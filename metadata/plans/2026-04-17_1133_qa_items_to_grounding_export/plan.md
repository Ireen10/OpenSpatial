# 执行计划（Plan）：`qa_items` → grounding 训练导出

依据：`design.md`（已对齐：标注阶段不产出图像 bytes；导出前重绘）、`metadata/docs/training_data_format_zh.md`。

## 交付物清单

- 文档：本目录下 `plan.md`、`test_plan.md`；实现结束后补 `change_log.md`。
- 代码（按依赖顺序）：
  1. **标注任务**：`spatial_relation_2d` 不再向行里写入 `QA_images`（及任何图像 bytes）；问题/答案/meta 仍完整；必要时仍用 `VisualMarker` **仅用于**生成 question 文案依赖的文本（与现逻辑一致），但不把渲染结果写入持久化列。
  2. **管线持久化**：`BasePipeline` / `ImageBaseDataset` 的 `annotation_qa_metadata` 默认 `keep_data_columns` 去掉 `QA_images`；`qa_bundle.jsonl` / flat parquet 与上述一致。
  3. **导出器（新）**：在 `metadata` 包内增加可测试模块（例如 `openspatial_metadata.export.grounding_training` 或 `train_export`），实现：`visual_group_key`、分组、原图路径解析、按需 **延后重绘**（`VisualMarker` + `objects` bbox + `qa.meta`）、写出 `meta_prompt`/`data`/`id` 行 JSON；图像写入 **`images/part_{id:06d}.tar`**，并写出同 id 的 **`images/part_{id:06d}_tarinfo.json`**（结构见 `metadata/docs/training_data_format_zh.md`：`relative_path` → `offset_data` / `size` / `sparse`）；JSONL 写入 **`jsonl/part_{id:06d}.jsonl`**。本阶段 **至少** 跑通 **单 part**（例如 `part_000000`），目录与文件名须与文档一致，便于你肉眼验收。
  4. **CLI（可选本阶段或紧随）**：`openspatial-metadata export-training` 或子命令，参数：`--input *.metadata.jsonl`、`--image-root`、`--output-root`、分片/part 选项；实现阶段以最小可用为准。
- 配置示例：在 `metadata/configs/` 或文档中给一条最小导出调用示例（可与 demo 数据集路径挂钩）。

## 文档同步（与本变更一并交付）

- [ ] `metadata/docs/training_data_format_zh.md`：若实现细节与文档有出入（例如 tar 命名），在同一变更内修订。
- [ ] `metadata/docs/project_progress_zh.md`：**整轮**（plan → test → 实现 → 自测 → change_log）结束后更新一次（见 `docs_sync_convention_zh.md`）。
- [ ] `metadata/README.md`：若新增 CLI 子命令，补一句用法链接。

## 任务拆解

### 任务 1：标注阶段去除图像 bytes 与列

- **目标**：Parquet / bundle / flat 中不再包含 `QA_images` 列或图像 bytes；与设计一致。
- **涉及文件**（预期）：
  - `task/annotation/spatial_relation_2d.py`（`apply_transform` 不再设置 `QA_images`；若需保留 PIL 仅作内存计算，不序列化）
  - `pipeline/base_pipeline.py`（`keep_data_columns` 默认列表）
  - `dataset/image_base.py`（默认列、`_write_qa_bundle_jsonl` 的 omit 集）
  - `config/annotation/demo_2d_spatial_relation.yaml`（`keep_data_columns`）
- **完成条件**：跑通现有与 spatial_relation_2d 相关的单测；无对 `QA_images` 的硬依赖断言（改为仅 meta/question/answer）。

### 任务 2：实现 `visual_group_key` 与分组纯函数

- **目标**：对单条 `AnnotationQaItemV0.meta` 计算 key；对同一 `MetadataV0` 的 `qa_items` 列表聚类为若干组（原图一组多轮、不同 key 多行）。
- **涉及文件**：新建 `metadata/src/openspatial_metadata/export/` 下模块（名称以实现为准），仅依赖 schema + 纯函数，便于单测。
- **完成条件**：单测覆盖 `n_marked_boxes==0`、两 QA 同 key、两 QA 不同 key。

### 任务 3：延后重绘与图像资源写入

- **目标**：给定 `MetadataV0` + 磁盘上的原图、可选 `image_root`，对需框组生成与任务一致的带框图（使用现有 `VisualMarker` 与 object 几何）；写出到 **`{output}/images/part_{id:06d}.tar`**，并生成 **`{output}/images/part_{id:06d}_tarinfo.json`**（键为 tar 内 `relative_path`，值为 `offset_data` / `size` / `sparse`，与 `training_data_format_zh.md` 一致）；JSONL 中的 `image.relative_path` 必须与 tar 内路径一致。首版 **单 part**（`id=0`）即可满足端到端验收。
- **涉及文件**：导出模块 + 可选复用 `task/annotation/core/visual_marker.py`（注意避免循环导入：可抽 **薄封装** 或把「norm1000 → 像素框 + draw」放在 export 子模块）。
- **完成条件**：在临时目录跑通「一条 metadata + 一张本地图」的集成测试；缺 bbox 时行为符合 design（跳过或显式错误，在 test_plan 中固定）。

### 任务 4：组 → grounding JSONL 行

- **目标**：每组生成一行 JSON：`meta_prompt` 为 `[""]`，`data` 内 user/assistant 交替，仅首轮 user 含 image+text，后续 user 仅 text；`id` 为 `""`。
- **完成条件**：与 `training_data_format_zh.md` 中单轮/多轮示例结构一致；pytest 快照或字典相等断言。

### 任务 5：CLI 与端到端小样（可选优先级）

- **目标**：命令行或库 API 一次跑通：读 `*.metadata.jsonl` → 产出与文档一致的 **`images/` + `jsonl/`**（含 **`.tar` + `_tarinfo.json` + `.jsonl`**，至少 `part_000000`）。
- **完成条件**：`test_plan.md` 中 E2E 项通过；或明确推迟 CLI 并在收束检查中注明「仅库 API」，但 **目录与三种文件形态仍须满足**。

## 依赖与顺序

1. 任务 1 可与任务 2 并行（不同文件），但全仓库 green 需合并后一起跑测试。
2. 任务 3 依赖任务 2（分组）与任务 1（无 bytes 假设）。
3. 任务 4 依赖任务 2、3。
4. 任务 5 依赖 3、4。

## 非本阶段（显式推迟）

- 完整多 part tar 分片、checkpoint、分布式写入优化。
- `VisualMarker` 的「显式指定颜色」API：若当前重绘与线上一致性不足，在 `change_log` 中单独立项跟进。

## 收束检查（合并前）

- [ ] `test_plan.md` 中条目均已实现或标为推迟。
- [ ] `pytest` 相关用例通过。
- [ ] **端到端目录验收**：在临时或示例 `output_root` 下存在 `images/part_000000.tar`、`images/part_000000_tarinfo.json`、`jsonl/part_000000.jsonl`，且 tarinfo 顶层键与 JSONL 内 `relative_path` 可对应。
- [ ] `change_log.md` 已写（可与 `project_progress_zh.md` 同一提交或紧随其后）。
