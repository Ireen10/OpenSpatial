# 方案设计（Design）：2D 关系增强（image_plane）

> 目录：`metadata/plans/2026-04-16_0300_metadata_next/`  
> 状态：**讨论稿** — 与 `metadata/docs/metadata_spec_v0_zh.md` v0 对齐；**输入侧格式本阶段不冻结为唯一 schema**，通过 **adapter + 归一化层 + 过滤策略** 收敛到统一 metadata。

---

## 1. 背景与目标

### 1.1 背景

- **已明确**：metadata **输出**侧 v0 结构（`dataset` / `sample` / `image` / `objects` / `relations` 等）及 2D 关系语义（`ref_frame=image_plane` 下的 `left|right|above|below`），见 `metadata/docs/metadata_spec_v0_zh.md`。
- **未明确**：上游 **输入** 可能是多种 JSON/Parquet/检测器导出形态；同一逻辑下物体数量、bbox 尺度、重叠程度变化很大。
- **本轮范围**：先只做 **2D image_plane 关系增强**，不碰 3D、不强制本轮完成 Parquet 主链路。

### 1.2 目标（必须可验证）

1. 给定一个 **sample** 语义等价于：**一张图** + **若干物体**；每个物体有 **自然语言描述（或类别）**，且 **仅用框或仅用点之一** 做 2D grounding（**框与点互斥**，见 §2.2）。多目标 grounding 下 **一个 label 可对应多个框或多个点**，但 **每个框或每个点对应恰好一个物体实例**（展开为多条 `Object`）。在此之上 **计算或补全** `relations`（有序对、`predicate` ∈ {left, right, above, below}，`ref_frame="image_plane"`）。
2. 所有写入的 `relations` 均可追溯：**`source`**（如 `computed`）、**`evidence`**（建议含 `method`、`anchor_point_uv_norm_1000`、`target_point_uv_norm_1000`、`delta_uv` 等与规范 §4.1 一致的子集）。
3. **过滤策略可配置、可复现**：同一输入 + 同一配置 → 相同输出；过滤掉的物体/关系在 **`aux.enrich_2d`**（或等价命名）中留下统计与原因码，便于审计。

### 1.3 非目标

- **3D**、`egocentric` 关系、深度/点云几何。
- 本轮 **不**将上游输入冻结为仓库唯一标准格式（仅定义 **最小输入契约** 与 **adapter 入口**）。
- **不**保证对所有噪声输入「填满」关系：允许在严格过滤下 **输出空 `relations`**（显式优于胡填）。
- **检测式 NMS**：**本轮不实现**。多框重叠不作为「合并框」问题处理；重叠与歧义交给 **§4 可解释过滤**（面积、对级 tie、高 IoU+近中心等）与 **对称边去重**，**不以检测 mAP 为目标**。

---

## 2. 最小输入契约（与上游的接口）

> 实现上建议：`RawSample`（adapter 输出）→ `normalize_objects()` → `ObjectV0` 列表 → `pairwise_geometry()` → `RelationV0` 列表。

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
- **框 / 点互斥**：在**同一条 grounding 展开路径**上，**要么只用框、要么只用点**，**不同时**写入同一物体的 `bbox_xyxy_norm_1000` 与 `point_uv_norm_1000`。若上游混给，adapter 须在归一化前 **二选一**（策略可配置：优先框、或优先点、或报错），并在 `aux`/`provenance` 中记录取舍。
- **与 spec §3.3.1 的关系**：规范中「框与点长度一致则配对」适用于**同时提供**的两模态；本设计 **收紧为互斥**，不再对同一物体做框点配对。
- **重叠**：不在输入层做 NMS；交给 **§4** 在物体级与关系对级做可解释过滤。

### 2.3 「多个物体 / 重叠」在输入侧的解读

- **多个物体**：多条 `Object` 或同一 label 多几何展开 → 多个 `ObjectV0`（见 §3）。
- **重叠框**：保留为多个 object；是否参与关系边由 **§4.2**（如 `ambiguous_iou`）决定，**不合并框**。

---

## 3. 与 v0 输出结构的映射

- **`objects`**：沿用 `ObjectV0`；写入 `phrase`（描述）、**仅框或仅点之一**（`bbox_xyxy_norm_1000` 或 `point_uv_norm_1000`）、`quality`（如 `bbox_quality`）供下游过滤与 QA 难度分层。
- **`relations`**：沿用 `RelationV0`；本阶段固定：
  - `ref_frame = "image_plane"`
  - `predicate ∈ {"left","right","above","below"}`（与规范一致；实现可用 `components` 或仅 `predicate` 二选一，**须与现有 `RelationV0` 校验一致**）
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
- **`min_abs_delta_u` / `min_abs_delta_v`**：低于阈值则认为 **tie**，**不输出**该维度的 left/right 或 above/below（或输出带 `score=0` 的弱关系 — **推荐不输出**，减少噪声）。
- **主方向选择（互斥）**：若 `|delta_u| > |delta_v|` 则只标 **left/right**；否则只标 **above/below**（或按规范拆成两条 — **未决**：单主谓词 vs 双轴分解，见 §7）。
- **对称去重**：若已输出 `A left B`，则不再输出 `B right A`（除非业务需要双向；默认 **去重**）。
- **重叠 bbox**：若 IoU > `ambiguous_iou` 且中心距离 < `ambiguous_center_dist`，认为 **空间关系不可靠**，**丢弃**该对或整图降级（`aux` 记 `reason=heavy_overlap`）。

### 4.3 质量与可追溯

- 对保留的物体写入 `quality.bbox_quality` 建议枚举：`high|medium|low|unknown`（规则可由面积、边界贴边、是否被裁剪等推导）。
- 每条 `relation` 的 `evidence` 必须能复算：至少保存两点坐标与 `method`。

---

## 5. 核心流程（伪代码级）

```
raw = adapter.load(sample_source)  # 输入格式未冻结
objs = normalize_objects(raw, coord_policy)
objs = filter_objects(objs, object_filters)
rels = []
for (a, t) in ordered_pairs(objs):   # 顺序策略可配置：全组合 / 仅不同类 / 等
    if filter_pair(a, t, pair_filters):
        continue
    p = compute_predicate_image_plane(rep_point(a), rep_point(t), rules)
    if p is not None:
        rels.append(make_relation(a.id, t.id, p, evidence=...))
rels = dedupe_symmetric(rels)
attach_aux_enrich_stats(...)
```

---

## 6. 风险

- **输入格式漂移**：仅靠「最小契约」仍可能遇到字段缺失；依赖 adapter 显式报错 + `strict` 行为与现有 CLI 一致。
- **符号与规范**：`above/below` 与像素 `y` 轴向一致性错误会导致系统性反标；需 **单元测试黄金向量**（小图 2–3 框手算）。
- **组合爆炸**：`O(n^2)` 对在 `n` 很大时需 `max_objects_per_sample` + 仅采样部分对（若未来需要，另开设计）。

---

## 7. 未决问题（需你确认）

1. ~~**同一文本多个 bbox / NMS**~~ **已定**：**一框或一点对应一个物体**；多 label 多几何则 **展开多 `ObjectV0`**；**框点互斥**；**不做 NMS**。上游 `count` 可用于一致性校验（可选），**不**用于合并框。
2. **主方向互斥 vs 双谓词**：一对 `(A,B)` 是只产 **一个** predicate，还是在 `|du|`≈`|dv|` 时产两条弱边或丢弃？
3. **第一轮交付形态**：优先 **库函数 + 单测**（`openspatial_metadata.enrich.relation2d`），还是同时接 **CLI 子命令**（如 `openspatial-metadata enrich-2d --config ...`）？
4. **与 adapter 的关系**：2D enrich 是 **PassthroughAdapter 之后的一步**，还是 **新 adapter 接口**（`enrich(sample: MetadataV0) -> MetadataV0`）？
5. **上游混给框+点**：adapter 二选一策略默认 **优先框**、**优先点** 还是 **strict 报错**？

---

## 8. 文档与实现对齐清单（design 对齐后执行）

- 更新 `metadata/docs/metadata_spec_v0_zh.md` 仅当引入与 §4.1 **不一致** 的新字段；否则在 `config_yaml_zh.md` / README 增加 **enrich 配置节** 即可。
- `plan.md` / `test_plan.md`：在 §7 确认后编写任务拆解与黄金向量测试表。
