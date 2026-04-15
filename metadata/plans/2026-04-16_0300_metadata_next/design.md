# 方案设计（Design）：2D 关系增强（image_plane）

> 目录：`metadata/plans/2026-04-16_0300_metadata_next/`  
> 状态：**已定稿（实现以本文为准）** — 与 `metadata/docs/metadata_spec_v0_zh.md` v0 对齐；**输入侧格式本阶段不冻结为唯一 schema**，由 **adapter** 将上游转为 **`MetadataV0`**；**enrich 与 adapter 解耦**，仅在 `MetadataV0` 上补全 `relations` 等（见 §2.2、§7）。

---

## 1. 背景与目标

### 1.1 背景

- **已明确**：metadata **输出**侧 v0 结构（`dataset` / `sample` / `image` / `objects` / `relations` 等）及 2D 关系语义（`ref_frame=image_plane`；**原子标签**为 `left|right|above|below`；**复合方位**由 **`components`** 与可选 **`axis_signs`** 表达，见 `metadata/docs/metadata_spec_v0_zh.md` **§2.3**、**§4.1**）。
- **未明确**：上游 **输入** 可能是多种 JSON/Parquet/检测器导出形态；同一逻辑下物体数量、bbox 尺度、重叠程度变化很大。
- **本轮范围**：先只做 **2D image_plane 关系增强**，不碰 3D、不强制本轮完成 Parquet 主链路。

### 1.2 目标（必须可验证）

1. 给定一个 **sample** 语义等价于：**一张图** + **若干物体**；每个物体有 **自然语言描述（或类别）**，且 **仅用框或仅用点之一** 做 2D grounding（**框与点互斥**，见 §2.2）。多目标 grounding 下 **一个 label 可对应多个框或多个点**，但 **每个框或每个点对应恰好一个物体实例**（展开为多条 `Object`）。在此之上 **计算或补全** `relations`（有序对、`ref_frame="image_plane"`）：输出可为 **单原子** `predicate`，或 **复合方位**（如左上、右下）下 **`components`** 含两个原子标签，与规范及 `RelationV0` 一致（见 §3）。
2. 所有写入的 `relations` 均可追溯：**`source`**（如 `computed`）、**`evidence`**（建议含 `method`、`anchor_point_uv_norm_1000`、`target_point_uv_norm_1000`、`delta_uv` 等与规范 §4.1 一致的子集）。
3. **过滤策略可配置、可复现**：同一输入 + 同一配置 → 相同输出；过滤掉的物体/关系在 **`aux.enrich_2d`**（或等价命名）中留下统计与原因码，便于审计。

### 1.3 非目标

- **3D**、`egocentric` 关系、深度/点云几何。
- 本轮 **不**将上游输入冻结为仓库唯一标准格式（仅定义 **最小输入契约** 与 **adapter 入口**）。
- **不**保证对所有噪声输入「填满」关系：允许在严格过滤下 **输出空 `relations`**（显式优于胡填）。
- **检测式 NMS**：**本轮不实现**。多框重叠不作为「合并框」问题处理；重叠与歧义交给 **§4 可解释过滤**（面积、对级 tie、高 IoU+近中心等）与 **对称边去重**，**不以检测 mAP 为目标**。

---

## 2. 最小输入契约（与上游的接口）

> **Adapter**：只负责把上游数据 **转换成合法的 `MetadataV0`**（含 `objects` 等），**不包含** 2D 关系计算逻辑。  
> **Enrich**：输入 **`MetadataV0`**，在 **同一数据结构**上写入/覆盖 `relations`（及 `aux.enrich_2d` 等），**不依赖**具体 adapter 类名；可在 CLI 管线中置于 adapter 之后调用，但二者 **模块级解耦**。

**最小字段（逻辑上必需）**

| 逻辑字段 | 说明 |
|----------|------|
| `image_ref` | 可解析的图片路径或 URI；用于 `sample.image.path` 与调试。 |
| `objects[]` | 每项：`local_id`（或可由序生成）、`text`（描述或类别）、以及 **`bbox_xyxy` 或 `point_uv` 二选一**（见 §2.2、坐标）。 |

### 2.1 坐标

- **框**：上游可能是 **像素 xyxy**、**归一化 0–1**、或 **已与 v0 一致的 `norm_0_999` + scale=1000**；归一化层统一为 **`bbox_xyxy_norm_1000`**。
- **点**：上游可为像素 `uv` 或归一化点；归一化层统一为 **`point_uv_norm_1000`**（与 `ObjectV0` 一致）。
- 全 sample 记录 `sample.image.coord_space` / `coord_scale`。

### 2.2 多目标 grounding、一实例一几何、框点互斥（已定）

- **一个框或一个点 ↔ 一个物体**：多目标 grounding 时，同一 **label/text** 可对应 **多个框或多个点**；每出现一个框或一个点就 **展开为一个 `ObjectV0`**（各自稳定的 `object_id`），**不**把多框合成一个检测框。
- **框 / 点互斥**：在**同一条 grounding 展开路径**上，**要么只用框、要么只用点**，**不同时**写入同一物体的 `bbox_xyxy_norm_1000` 与 `point_uv_norm_1000`。若上游对**同一物体实例**混给框+点，**adapter 在生成 `MetadataV0` 时须报错退出**（**已定**：不采用优先框/优先点静默取舍）。`enrich` 入口可对已存在 `MetadataV0` 做防御性校验，发现混用同样报错。
- **与 spec §3.3.1 的关系**：规范中「框与点长度一致则配对」适用于**同时提供**的两模态；本设计 **收紧为互斥**，不再对同一物体做框点配对。
- **重叠**：不在输入层做 NMS；交给 **§4** 在物体级与关系对级做可解释过滤。

### 2.3 「多个物体 / 重叠」在输入侧的解读

- **多个物体**：多条 `Object` 或同一 label 多几何展开 → 多个 `ObjectV0`（见 §3）。
- **重叠框**：保留为多个 object；是否参与关系边由 **§4.2** 写死的 IoU/近中心规则决定，**不合并框**。

---

## 3. 与 v0 输出结构的映射

- **`objects`**：沿用 `ObjectV0`；写入 `phrase`（描述）、**仅框或仅点之一**（`bbox_xyxy_norm_1000` 或 `point_uv_norm_1000`）、`quality`（如 `bbox_quality`）供下游过滤与 QA 难度分层。
- **`relations`**：沿用 `RelationV0`（`predicate`、`components`、`axis_signs` 均为模型已有字段）。本阶段固定：
  - `ref_frame = "image_plane"`
  - **原子标签集**（规范 **§2.3**）：`left|right|above|below`。**复合方位**（如 **左上、右上、左下、右下**）**不**引入规范外的新字符串作唯一真源，而用：
    - **`components: List[str]`**：长度 1 时可与单 `predicate` 同义；长度 **≥2** 时表示复合，例如 `["left","above"]`（左上）、`["right","below"]`（右下）；列表元素 **必须** 属于上述四原子之一。
    - **可选 `axis_signs`**：与规范 **§4.2.1** 同一符号思想在 **2D 子集**上表达，**仅**使用键 `right` 与 `above`（不写 `front`），取值 `-1|0|+1`，与 `components` **语义一致、可互相校验**。
  - **`predicate` 与 `components` 的填写约定（本轮）**：  
    - **仅单轴显著**：只填 **`predicate`** 为对应原子，`components` 可省略或单元素（实现二选一但须**自洽且可测**）。  
    - **双轴均显著（复合）**：**必须**填 **`components`** 为两个原子（顺序约定：**先水平 `left|right`，后垂直 `above|below`**）。**`predicate`** 与 **`components[0]`（水平腿）一致**，仅作与 `RelationV0.predicate` 必填字段的兼容；**复合语义以 `components` 为准**，不再用 `|du|`/`|dv|` 大小选「主谓词」、**不**因两轴幅度接近而丢弃。
  - `source = "computed"`（或规范中的 `"computed"`）
  - `evidence`：至少 `method`（`bbox_center` 或 **`point_uv`**，与物体几何一致）、参与计算的代表点、`delta_uv`（可选）
- **`aux.enrich_2d`**（建议结构，可调整命名）：
  - `config_hash` 或序列化后的过滤配置快照
  - `dropped_objects: [{object_id, reason, ...}]`
  - `dropped_relation_candidates: [{anchor_id, target_id, reason}]`
  - `stats: {n_objects_in, n_objects_kept, n_pairs_considered, n_relations_out}`

---

## 4. 过滤与消歧策略（设计重心）

以下策略建议 **全部做成配置项**（YAML 或 dict），默认值偏保守（宁可少产关系）。

### 4.1 物体级过滤（进入关系计算之前）

| 策略 ID | 含义 | 建议默认思路 |
|---------|------|----------------|
| `geom_valid` | 剔除非法框：`x1>=x2`、`y1>=y2`、面积为 0、NaN；**点模式**下剔除 `uv` 越界或 NaN | 必做 |
| `in_bounds` | 裁剪或剔除超出 `[0, coord_scale)` 的框；若裁剪后面积低于阈值则剔除 | 可配置「裁剪 vs 剔除」；**点模式**仅做 `uv` 边界检查 |
| `min_area_abs` | 绝对最小面积（归一化平方单位） | **仅框**；抑制极小块噪声 |
| `min_area_frac` | 相对整图面积的最小占比 | **仅框**；抑制极小目标 |
| `max_aspect_ratio` | 宽高比上限 | **仅框**；抑制条状异常框 |
| `max_objects_per_sample` | 单图最多保留 K 个物体 | 超大列表时按 **面积降序**（框）或 **固定序+点权**（点）或 **随机种子固定** 保留，并记 `reason=cap_exceeded` |

（**不包含** `nms_iou`：本轮不做 NMS。）

### 4.2 关系对级过滤（有序对 `(anchor, target)`）

- **几何代表点（默认）**：有框则用 **bbox 中心**；仅有点则用 **`point_uv_norm_1000`**。比较 `delta_u`、`delta_v`（v 向下为正，则 **image_plane 的 above = 更小 v** 须在实现与文档中写死一处，避免符号反了）。
- **`min_abs_delta_u` / `min_abs_delta_v`**：某轴 `|delta|` 低于阈值则该轴视为 **tie**，不参与该轴的原子输出。
- **单原子 vs 复合（已定）**：
  - **仅水平轴显著**（竖直为 tie）：只输出 **`predicate`** ∈ {left, right}（及可选 `components: ["left"]` 等自洽形式）。
  - **仅竖直轴显著**：只输出 **`predicate`** ∈ {above, below}。
  - **两轴均显著**：输出 **`components: [水平原子, 垂直原子]`**（§3 顺序约定）；**`predicate` = `components[0]`**；不因 `|du|≈|dv|` 丢弃。
- **对称去重（写死）**：全组合遍历时对无序对 `{A,B}` **只产一条**有向边（例如固定 **字典序较小的 `object_id` 为 anchor**）；单原子与复合均适用。不引入「是否双写」配置项。
- **重叠度过高或中心过近（写死）**：**不作可配置开关**。若 **两物体 bbox IoU 高于代码内定常量**，**或** **两物体代表点（框中心或点坐标）在归一化平面上的距离低于代码内定常量**，则 **直接丢弃该有序对**（不参与谓词计算）。`aux` 中记录丢弃原因（如 `high_iou`、`near_center`）即可。阈值仅在实现里维护，调参若需暴露再单开一轮设计。

### 4.3 质量与可追溯

- 对保留的物体写入 `quality.bbox_quality` 建议枚举：`high|medium|low|unknown`（规则可由面积、边界贴边、是否被裁剪等推导）。
- 每条 `relation` 的 `evidence` 必须能复算：至少保存两点坐标与 `method`。

### 4.4 写死阈值与坐标归一化（`0 … coord_scale`，通常 1000）

**会不会有问题？** — 在仓库已约定 **v0 物体坐标与 `coord_scale`（常见为 1000）同一套归一化空间** 的前提下，**阈值写死在代码里没有尺度矛盾**：距离、面积、`min_abs_delta_*`、近中心阈值、IoU 等，全部理解为 **「与该 sample 的 `sample.image.coord_scale` 一致的归一化单位」** 下的常数（开发时常在 `coord_scale=1000` 下标定一组整数/浮点常量）。

**仍须注意的两点**（实现时写进模块 docstring 即可）：

1. **与 `coord_scale` 一致**：若某条 metadata 的 `coord_scale` **不是** 1000，**不得**仍用「为 1000 标定」的裸常数去比；应 **`effective_scale = metadata.sample.image.coord_scale or 1000`**，并将标定常量 **按 `effective_scale / 1000` 比例换算**（或直接把常数定义为 **`k * effective_scale` 的分数**，例如近中心距离 = `0.02 * effective_scale`），避免换 scale 后「同一物理语义、阈值却错一档」。
2. **与 YAML 解耦不等于不可维护**：常量集中在一个模块（如 `enrich/constants.py`）+ 注释写明「在 scale=1000 下等价于约 N 像素若全幅宽约 W」之类，便于日后单开一轮把少数阈值暴露为配置，而**无需**本轮改设计。

---

## 5. 核心流程（伪代码级）

```
raw = adapter.load(sample_source)  # 输入格式未冻结
objs = normalize_objects(raw, coord_policy)
objs = filter_objects(objs, object_filters)
rels = []
for (a, t) in ordered_pairs(objs):   # 首轮写死：全组合经对称规则压成无序对一条有向边
    if filter_pair(a, t, pair_filters):
        continue
    rel = compute_relation_image_plane(rep_point(a), rep_point(t), rules)  # 单原子或带 components
    if rel is not None:
        rels.append(rel)
attach_aux_enrich_stats(...)
```

---

## 6. 风险

- **输入格式漂移**：仅靠「最小契约」仍可能遇到字段缺失；依赖 adapter 显式报错 + `strict` 行为与现有 CLI 一致。
- **符号与规范**：`above/below` 与像素 `y` 轴向一致性错误会导致系统性反标；需 **单元测试黄金向量**（小图 2–3 框手算）。
- **组合爆炸**：`O(n^2)` 对在 `n` 很大时需 `max_objects_per_sample` + 仅采样部分对（若未来需要，另开设计）。

---

## 7. 已定决策摘要（原未决项收口）

1. **多 bbox / NMS**：一框/一点一物体；展开多 `ObjectV0`；**不做 NMS**。
2. **单轴 vs 复合**：双轴显著 → **`components`** + **`predicate`=水平腿**；单轴 → **`predicate`**；**无**「平局带丢弃」。
3. **交付形态**：**首轮仅库 + 单测**（如 `openspatial_metadata.enrich.relation2d`）；**不接新 CLI 子命令**（与 CLI 的串接留待后续若需要再开 plan）。
4. **与 adapter**：**解耦** — adapter 只做 **→ `MetadataV0`**；enrich 只做 **`MetadataV0` → 补全 `relations` 等**，**不是** adapter 子类、**不**新增 `enrich()` 作为 adapter 接口；管线顺序上可为「adapter 后调用 enrich 函数」。
5. **框+点混用**：**报错**（adapter 生成阶段；enrich 可防御性再校验）。

**仍可在实现中微调、无需再开 design 的**：物体级过滤各阈值的默认数值、`aux.enrich_2d` 键名细粒度；若与本文冲突须回写 design。

---

## 8. 文档与实现对齐清单（design 对齐后执行）

- `metadata/docs/metadata_spec_v0_zh.md` §4.1 已与 **§2.3** 对齐；字段名变更须同步。
- `metadata/docs/config_yaml_zh.md` / `README.md`：若 enrich 暴露 YAML 则增一节；**首轮仅代码常量 + 可选函数参数**时可只更新 README「库 API」一句。
- `plan.md` / `test_plan.md`：随本轮实现勾选。
