## Metadata 可视化（v0）设计

### 背景与目标

`metadata` 子工程目前已经能稳定产出 `*.metadata.jsonl`，并在 `relations` 中（可选）附带 2D enrich 结果。可视化模块的目标是：

- 让数据/算法/标注/评测同学可以**快速理解单条 sample 的结构与质量**（objects / queries / relations / aux）。
- 让调参/排查更高效：能看到 enrich 的“为什么算成这样 / 为什么被过滤掉”。
- 为后续 3D（`egocentric`）关系、以及多数据集接入提供可扩展的展示骨架。

非目标（v0 不做）：

- 不做复杂的编辑/回写（只读为主）。
- 不做跨样本全局统计大屏（先把单样本 debug 体验做扎实）。
- **不处理 3D relation 的可视化**：当前管线未产出 3D 关系数据；UI 对 `ref_frame=egocentric`（及预留的 `allocentric`）仅做**列表旁路展示**（标签/字段只读），不画 3D 示意、不依赖 depth/camera。

---

### 输入数据与范围

#### 支持的输入（v0 收窄）

- **唯一一类主输入**：`openspatial-metadata` 产出的 **`*.metadata.jsonl`**（每行一条 `MetadataV0` 记录）。不读取 adapter 前的原始 JSONL、不读取其它格式。

##### 与 CLI 输出目录的对应关系（代码约定）

`openspatial-metadata` 将写出目录定为：

- `{output_root} / {dataset.name} / {split.name} /`
- 其中 `output_root` 来自 CLI `--output-root`、global 配置的 `output_root`，或某数据集 `dataset.yaml` 里的 `output_root`（见 `metadata/src/openspatial_metadata/cli.py`：`out_dir = output_root / ds.name / split.name`）。
- 该目录下的产物文件名包括：
  - **jsonl 输入**：`{输入文件主名}.metadata.jsonl`（与每个输入 shard 一一对应）；
  - **json_files 输入**：`part-{序号}.metadata.jsonl`（聚合分片）。
- 子目录 **`.checkpoints`** 仅含断点 JSON，**不参与** metadata 浏览列表。

##### 交互形态（两种等价入口，数据形态不发散）

1. **单文件**：用户选择或拖入**某一个** `*.metadata.jsonl`，在当前文件内 **上一条 / 下一条** 逐行浏览；可选按 `sample.sample_id` 在**当前已打开文件**内跳转（需建立行索引或线性扫描，见实现阶段）。
2. **绑定整个 output_root（推荐批量排查）**：用户指定一个 **`output_root`**（例如 `metadata_out` 或某数据集单独配置的根），工具在磁盘上**枚举**其下全部 metadata 产物（仍仅限 `**/*.metadata.jsonl`），按 **`数据集名（目录名）→ split 名 → 文件`** 三级结构展示，便于快速切换「看哪个数据集的哪个 split 的哪个 shard」。
   - **不要求**把整个 output_root 一次性读入内存：仅缓存**目录树与文件列表**；打开某个文件后再按**行**懒加载（或 mmap/流式读当前行），上一条/下一条只维护「当前文件路径 + 行号」。
   - 与 (1) 的关系：(1) 等价于在 (2) 里只注册了一个文件。

仍不扩展：原始对话 JSONL、非 `*.metadata.jsonl` 后缀、以及将其它目录误当作数据集根（除非用户显式绑定为 `output_root`）。

#### v0 重点展示字段（与当前代码/样例一致）

- 顶层：`dataset / sample / camera / objects / queries / relations / aux`
- `sample.image`：`path/width/height/coord_space/coord_scale`
- `objects[]`：`object_id/category/phrase/bbox_xyxy_norm_1000/point_uv_norm_1000/mask_path/quality`
- `queries[]`：`query_id/query_text/query_type/candidate_object_ids/gold_object_id/count/filters`
- `relations[]`：`anchor_id/target_id/predicate/ref_frame/components/axis_signs/source/score/evidence`
  - 2D enrich evidence 形态（当前实现）：`method/anchor_point_uv_norm_1000/target_point_uv_norm_1000/delta_uv`
- `aux`：`record_ref`、`adapter_*`、`enrich_2d.*`

---

### 目标用户与典型任务

- 数据工程/算法：
  - 快速确认 adapter 是否解析对了（objects/queries 数量、bbox 坐标合理、警告原因）。
  - 快速确认 enrich 是否合理（关系方向、阈值过滤/去重、代表点）。
- 标注/QA：
  - 对照图像查看 query 文本是否能指向对应 object。
  - 查看多实例 query 的候选集合是否符合 count。
- 评测：
  - 抽样 spot-check：关系标签与 ref_frame 是否匹配预期。

---

### 交互与信息架构（IA）

整体采用“两栏 + 画布”的结构：

#### A. 顶部：样本头部栏（Header）

- Dataset：`dataset.name/split/version/source`
- Sample：`sample.sample_id`
- Input trace：`aux.record_ref.input_file` + `input_index`
- 快捷操作：复制 sample_id、复制当前 JSON（折叠/展开）

#### B. 中央：图像画布（Canvas）

在图像上叠加：

- **Objects overlay**
  - bbox（矩形框）/ point（十字或圆点）
  - object_id 标签（可配置显示：仅 hover 显示 / 总显示）
  - 支持点击高亮单个 object（联动右侧列表）
- **Queries overlay（可选）**
  - 选中某个 query 时：高亮该 query 的候选 objects（多实例用同一颜色体系）
- **Relations overlay（可选）**
  - `ref_frame="image_plane"`：在 anchor/target 的代表点之间画箭头或连线；颜色按 predicate/components 区分
  - 选中某条 relation 时：显示 evidence 面板（anchor/target 代表点、delta_uv）

> 注意：当前 enrich 的代表点基于 bbox center 或 point 本身；可视化应显示“代表点”而不是隐含。

#### C. 右栏：信息面板（Inspector）

分 Tabs（或折叠区块）：

1) **Objects**
   - 表格：object_id / phrase / category / bbox or point / quality / mask_path
   - 点击一行 → 画布高亮
   - 支持过滤：仅 bbox、仅 point、quality 过滤（若存在）

2) **Queries**
   - 列表：query_text / query_type / count / gold
   - 展开：candidate_object_ids（点击联动 objects）
   - 异常提示：count 与候选长度不一致、gold 不在候选里等

3) **Relations**
   - 支持按 `ref_frame` 分组；**v0 画布与箭头仅实现 `image_plane`**。
   - 对 **`egocentric` / `allocentric`**：仅在列表中展示字段（旁路），**不绘制空间箭头**（当前无 3D 数据、也不引入新依赖）。
   - `image_plane`：每条显示 anchor_id → target_id、predicate、components、source、score；选中后展示 evidence（方法、代表点、delta）
   - 辅助：根据 `components` 生成“左上/右下”等友好标签（仍以原始字段为准）

4) **Aux / Debug**
   - `adapter_stats / adapter_warnings`
   - `enrich_2d.stats`、`dropped_objects`、`dropped_relation_candidates`
   - checkpoint/路径等仅做展示不编辑

---

### 可视化细节规则（与数据定义对齐）

#### 坐标与缩放

- bbox/point 字段名为 `*_norm_1000`，语义是「归一化到 `[0, coord_scale)` 的整数网格」；**比例尺以记录为准**。
- **首选**：`scale = sample.image.coord_scale`（adapter/CLI 写入，与生成 metadata 时所用刻度一致）。
- **兜底**：若某条记录缺失 `coord_scale`，可使用运行时可读配置中的默认值；该默认值应与管线一致——例如 **`metadata/configs/global.yaml` 的 `scale`**（当前为 `1000`），与 `GroundingQAAdapter(..., coord_scale=...)` 注入值对齐。
- 画布映射：
  - \(x_{px} = x_{norm} / scale * width\)
  - \(y_{px} = y_{norm} / scale * height\)
- 若 `width/height` 缺失：从解码后的图像读取实际尺寸后再绘制（或提示用户）。

#### 关系方向

- enrich 约定：`delta_uv = target - anchor`，predicate 表达 **target 相对 anchor**。
- “above” 在 image_plane 下意味着 `dv < 0`（因为 y 向下增）。
- 复合关系：当前实现会在 `components` 同时写 `["left","above"]`，但 `predicate` 只保留水平分量（left/right）——可视化时应以 `components` 为准展示复合方向。

#### 不一致/异常提示（v0 直接提示，不阻断）

- object 同时有 bbox 与 point：当前 enrich 会报错；可视化可提前标红
- query.count 与 candidates 长度不一致
- relation 引用的 object_id 不存在
- bbox 坐标越界/无效（x1>=x2 等）

---

### 架构方案

**v0 采用「轻本地后端 + 前端」**：仅支持读取用户提供的 **`*.metadata.jsonl`** 与本地图像资源；后端负责 JSONL 流式/分页、**按规则解析 `sample.image.path` 为图像字节或 URL**、可选提供 `width/height` 兜底。纯静态前端无法可靠读取任意本机路径与 tar 内文件，故不作为主路径。

---

### `sample.image.path` 的解析策略（与 refcoco README 对齐）

`metadata/configs/datasets/refcoco_grounding_aug_en_250618/README.md` 说明：图像在数据侧以 **`images/part_{id}.tar`** 存储，tar 内以 **`relative_path`**（与 metadata 中 `sample.image.path` 一致）索引；另有 **`part_{id}_tarinfo.json`** 将 `{image_relative_path} -> { offset_data, size }`，支持不经全量解压、按偏移读二进制。

因此 **`sample.image.path` 不一定是「某固定磁盘根目录下的相对路径」**，更可能是 **「tar 包内的路径」**。可视化需支持多种来源，按优先级尝试（可配置、可开关）：

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| **A. 解压目录（扁平文件树）** | 配置 `image_root`：存在则尝试 `Path(image_root) / sample.image.path`。 | 用户已把 tar 解到同一根目录，路径与 tar 内一致。 |
| **B. tar + tarinfo（推荐与 README 一致）** | 配置 `images_base_dir` 指向含 `part_*.tar` 与 `part_*_tarinfo.json` 的目录；启动或首次请求时合并所有 `*_tarinfo.json`，建立 **`relative_path -> (tar_path, offset, size)`** 索引；按偏移从对应 `.tar` 读取字节流并作为 `image/jpeg` 响应（或缓存到临时文件）。 | 未解压、仅有分卷 tar + json 索引。 |
| **C. 可选规则插件（预留）** | 若某数据集存在确定性规则（例如路径前缀与 `part_id` 对应），可实现小模块 **path → tar 文件名**；无规则时不启用。 | README 未写死映射时仅占位，避免臆造。 |

**配置落点（已与产品对齐）：**

- **主路径：复用各数据集的 `dataset.yaml`**。在配置中增加可选块（例如 `viz:`），至少包含 **`image_root`**（解压后的扁平图像根，模式 A），与 `sample.image.path` 拼接读图。同一文件内已有 **`output_root`**（与 `openspatial-metadata` 写出目录一致）时，可视化直接复用，避免再输一遍根路径。
- **兜底**：CLI/全局 **`global.yaml`** 的 `output_root`、`scale` 仍可作为未在 `dataset.yaml` 声明时的默认值（与现有 ingestion 行为一致）。
- **可选后续**：独立 `metadata_viz.yaml` 或环境变量仅作覆盖，不作为 v0 必选项。
- 不在每条 metadata 内强制写入 `abs_path`（避免绑定单机路径）；若团队希望可插拔地增加 `sample.image.uri` 由离线脚本注入，可作为后续增强。

**失败时的 UI**：明确提示「当前 path 在 flat/tar 索引中均未命中」，并展示原始 `sample.image.path` 与已配置的根路径，便于排查。

---

### 已拍板 / 建议约定（本轮）

| 项目 | 约定 |
|------|------|
| 输入 | 仅 **`*.metadata.jsonl`** |
| Object 展示名 | **`phrase` > `category` > `object_id`**；不强制改 adapter |
| 3D relation | **旁路**：仅列表展示字段，画布不画 3D |
| `coord_scale` | 以 **`sample.image.coord_scale`** 为准；缺失时回退 **`global.yaml` 的 `scale`**（与管线一致） |

---

### 仍属可选/后续（不阻塞 v0）

- **mask**：`mask_path` 多为空；若将来有值，再定义与 `sample.image.path` 同源还是独立根路径。
- **路径规则插件**：仅当某数据集文档明确写出 `relative_path` → `part_id` 的映射时再实现。

---

### v0 可交付物（设计层面）

- 单 sample viewer：
  - 画布（`image_plane` 的 objects / relations overlay）
  - 右侧 inspector（objects/queries/relations/aux；3D 类 relation 仅文本）
  - 输入：
    - **绑定 `output_root`**：`{output_root}/{dataset}/{split}/*.metadata.jsonl` 树形选择 + 当前文件内上一条/下一条；`sample.sample_id` 跳转可在单文件内实现（全量索引可选，见实现阶段）。
    - **单文件拖入**：与上条等价，仅注册一个文件。
  - 内存：目录树轻量；**不**要求预加载所有 JSONL 内容。
- 图像：`image_root` 扁平 **或** `images_base_dir` + tarinfo 索引，见上文「解析策略」

