# Design：从 `qa_items` 导出 grounding 式训练数据

## 文档依据

- 训练 JSONL / 多轮与分组语义：`metadata/docs/training_data_format_zh.md`
- 元数据与 QA 一等公民字段：`metadata/src/openspatial_metadata/schema/metadata_v0.py`（`MetadataV0.qa_items` / `AnnotationQaItemV0`）
- 2D 关系任务写入的逐条 `meta`：`task/annotation/spatial_relation_2d.py`（含 `relation_id`、`marked_roles`、`mark_colors`、`n_marked_boxes` 等）

## 目标

1. 从 **带 `qa_items`** 的 metadata（每行一条 `MetadataV0`）导出 **grounding 兼容** 的 JSONL（及按需打包的图像资源），满足 `training_data_format_zh.md` 中的 **`meta_prompt` / `data` / `id`** 约定。
2. 按 **分组规则** 将同一 sample 下多条 QA 拆成 **多行训练样本**（每组一行），组内 **单轮或多轮** `user`/`assistant` 交替；**首轮 user 前**仅一条 image 部件，其后仅 text。
3. **`id` 不影响训练**：允许固定为空字符串；不在本设计范围内引入命名方案。

## 非目标（本阶段）

- 不规定业务侧最终 `id` 命名规则。
- 不替代上游 **原始 grounding** 数据管线；仅定义 **OpenSpatial 生成 QA → 同构 JSONL** 的路径。
- 不实现完整分布式 tar 分片策略的细节（可在 plan 中列为配置项），仅约定 **相对路径与目录布局** 与 `training_data_format_zh.md` 一致。

## 输入假设

- 每条 metadata **至少**包含：`dataset`、`sample`（含 `sample.image` 与 `sample_id`）、`qa_items`。
- 每个 `AnnotationQaItemV0` **至少**包含：`qa_id`、`question`、`answer`、`meta`（任务侧已写入结构化字段）；可选 `relation_id`（可与 `meta["relation_id"]` 对齐）。
- **框的几何**：**不**依赖在 `meta` 里重复存像素坐标。`spatial_relation_2d` 在 `meta` 中保存 **`anchor_id` / `target_id`**、**`marked_roles`**、**`mark_colors`**、**`n_marked_boxes`** 等；**框坐标**在 **`MetadataV0.objects[].bbox_xyxy_norm_1000`**（及 `object_id`），导出时用 id 关联即可。
- **延后绘制（强约束）**：标注阶段 **不产出任何图像 bytes**，不写 `QA_images`、不写带框 PNG。只要 **metadata 行**上 `objects` 与 `qa_items[].meta` 完整，在 **转成训练数据之前** 用原图 + `VisualMarker`（`mark_type=box`）按 `marked_roles` / `mark_colors` + object 几何 **重绘** 生成所需的带框图即可。
- **区分「不同图片」的 id**：实现中任意 **稳定字符串** 即可（例如 `visual_group_key` 或 `sha256(渲染后字节)`）；不要求业务 `id` 字段。

## 分组：从语义到可实现键

训练文档中的分组意图：

| 组类型 | 语义 | 实现要点 |
|--------|------|----------|
| **原图组** | 不画新框、视觉输入为 **原图** | `meta["n_marked_boxes"] == 0`（或与任务约定一致的「无框」判定） |
| **渲染图组** | 需框、且 **同一张渲染图** 共用 | 需在组内共用同一 image 部件指向的路径 |

**「完全相同框绘制」** 的可计算定义（在不增加新标注任务字段的前提下，以当前 `spatial_relation_2d` 的 `meta` 为准）：

- 定义 **`visual_group_key`（字符串，仅用于分组）**：
  - 若 **`n_marked_boxes == 0`**：`visual_group_key = "original"`（该 sample 下所有原图 QA 先进同一候选池，再按「仅一条原图组」或「多条合并多轮」见下）。
  - 若 **`n_marked_boxes > 0`**：`visual_group_key = stable_repr(`marked_roles` 排序后) + `#` + stable_repr(`mark_colors` 按键排序后的 (role→color) 列表) + `#` + `n_marked_boxes`。  
  - 说明：同一框配色与同一组标记角色在任务里应产生 **同一渲染语义**；若未来出现 **像素相同但 meta 略不一致** 的边界情况，可在实现阶段改为对 **渲染图内容哈希** 作为二次归并键（本设计保留扩展位）。

**同一 sample 内多条「原图」QA**：共享 `visual_group_key == "original"`，**合并为同一组**，在 `data` 内形成 **多轮**（文档已约定）。

**多条不同 `visual_group_key`**：各对应 **独立一行** JSONL（每组首轮各带自己的 image）。

## 输出结构（摘要）

与 `training_data_format_zh.md` 对齐，不重复全文：

- `meta_prompt`：`[""]`。
- `data`：`user`/`assistant` 严格交替；仅 **该组第一条 user** 的 `content` 以 **image** 开头，再接 **一条 text（question）**；每个 **assistant** 仅 **一条 text（answer）**。
- `id`：`""`（或配置恒等，直至业务定义命名）。

**组内 QA 顺序**：同一 `visual_group_key` 内，按 **`qa_items` 在 metadata 中的顺序**（若合并自多来源，则按 `qa_id` 字典序作为稳定备选）生成多轮。

## 流水线（逻辑模块）

以下为 **概念阶段**，实现时可落在 `metadata` CLI 子命令或独立脚本，由 `plan.md` 拆分任务。

1. **加载**：流式或批量读取 `*.metadata.jsonl`，解析为 `MetadataV0`。
2. **视觉输入就绪**：原图组 —— `sample.image.path` + `image_root`；需框组 —— **延后绘制**（原图 PIL + `objects` bbox + `qa.meta` 调 `VisualMarker`）。不读取也不依赖 `QA_images` 字节。
3. **分组**：对每个 sample 的 `qa_items` 计算 `visual_group_key`，聚类为若干组。
4. **写资源**：将原图 / 渲染图 **写入** `images/part_{id:06d}.tar`，并写出 **`images/part_{id:06d}_tarinfo.json`**（`relative_path` → `offset_data` / `size` / `sparse`，与 `training_data_format_zh.md` 一致）；得到 JSONL 中引用的 **`relative_path` + width + height**。
5. **组 → 行**：每组生成一行 JSON：`meta_prompt`、`data`（多轮）、`id`。
6. **写出**：`jsonl/part_{id:06d}.jsonl`（与 tar **同 part id**；本阶段可先仅 `part_000000`，多 part 切分推迟）。

## 与现有仓库组件的衔接

- **管线侧** 已有：`annotation_qa_metadata_stage` → `data.qa_bundle.jsonl` + `data_flat.parquet`（`dataset/image_base.py`）。**合并**「bundle / flat → 带 `qa_items` 的 metadata」若尚未实现，应在 **plan** 中作为 **前置或并行** 任务列出。
- **Schema**：`AnnotationQaItemV0.meta` 已能承载分组所需字段；若实现中发现需 **显式 `visual_group_key`**，可作为 **可选** 写入 `meta`（任务或合并步骤），以简化导出端逻辑。

## 风险与依赖

- **objects 缺 bbox**：若某 `anchor_id`/`target_id` 在 `objects` 中无 **`bbox_xyxy_norm_1000`**，则无法重绘带框图，该 QA 须在导出时 **跳过或报错**（与任务 `check_example` 一致时应极少发生）。
- **重绘与线上一致性**：延后绘制须使用与标注任务相同的 **归一化坐标系、MarkConfig、对象顺序（anchor/target 与 `marked_roles`）**；若将来改队列或配色，老数据需版本字段或继续依赖当时写入的 **`mark_colors`** 显式着色（实现层可对 `VisualMarker` 走「指定颜色」路径，若后续 API 补齐）。
- **`relation_id` 缺失**：不影响分组；影响追溯，由上游 `ensure_relation_ids` 与任务保证。
- **多 part / 大 tar**：性能与 checkpoint 属实现阶段优化项。

## 信息完整性结论

在 **`id` 不作为约束** 的前提下，**产品语义与格式** 已由 `training_data_format_zh.md` 覆盖；本设计补足了 **分组键的可计算定义**、**流水线模块边界** 与 **输入输出假设**。**不阻塞** 进入 `plan.md`（执行计划）与 **test_plan.md**；若你对 **`visual_group_key` 的字符串公式** 希望改为「仅对渲染图做内容哈希」，可在对齐 design 时改一节即可。
