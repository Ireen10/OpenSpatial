## 变更记录（Change Log）

### 变更摘要

- 本次新增/变更：
  - 在 `openspatial-metadata` CLI 中接入 dataset-level `pipelines` 执行路径，支持按“单条记录不中断”的方式在同一 worker 内串联：
    - `to_metadata`（可选：适配/补充 dataset meta/可选 enrich）
    - `ensure_qa`（可选：metadata-native QA 生成，写出带 `qa_items` 的 metadata）
    - `export_training`（可选：输出训练数据 bundle：`images/*.tar` + `*_tarinfo.json` + `jsonl/*.jsonl`）
  - 支持 `training_output_root`（dataset 级别）指定训练 bundle 输出根；新增 global `qa_config` 与 CLI `--qa-config` 入口加载全局 QA 任务注册表。
  - 新增训练导出增量写入实现（append tar/jsonl，结束后生成 tarinfo），并加入 tar member 路径冲突消歧规则 `__r{input_index}`。
- 影响范围：
  - `metadata/src/openspatial_metadata/cli.py`（CLI 主流程 + pipeline runner）
  - `metadata/src/openspatial_metadata/config/schema.py`（新增字段）
  - `metadata/src/openspatial_metadata/export/*`（stream writer、路径消歧、export helper）
  - `metadata/src/openspatial_metadata/config/qa_tasks.py` 与 `metadata/src/openspatial_metadata/qa/*`（QA 配置加载与 metadata-native QA）
  - `metadata/tests/`（新增 E2E 配置与测试）
- 兼容性说明：
  - 不配置 `pipelines` 时，CLI 保持原有 “metadata-only” 行为。
  - `qa_config`/`--qa-config` 为新增可选项；不启用 `ensure_qa/export_training` 时不会触发 QA/导出逻辑。

### 文档与对外说明

- 已更新的文档（路径列表）：
  - `metadata/plans/2026-04-17_1059_training_export_parallel_io/design.md`
  - `metadata/plans/2026-04-17_1059_training_export_parallel_io/plan.md`
  - `metadata/docs/config_yaml_zh.md`（补充 global.qa_config / dataset.training_output_root / pipelines 行为）
- 测试配置：
  - `metadata/tests/configs/e2e_training_pipeline/`（global + qa_tasks + dataset 示例）

### 与上一版差异

- 变更点列表：
  - 新增 dataset-level pipeline 入口：`pipelines.{to_metadata,ensure_qa,export_training,qa_task_name,qa_task_overrides}`
  - 全局 QA 配置集中管理：`global.yaml.qa_config` + CLI `--qa-config`
  - 训练 bundle 输出：`{training_output_root}/{dataset}/{split}/{images,jsonl}/part_*.{tar,jsonl} + *_tarinfo.json`
  - Resume：
    - jsonl 输入：按输入文件 checkpoint `next_input_index`
    - 导出：tar/jsonl append（同 part），最终 tarinfo 重算写出
- 删除/废弃点：
  - 无（本阶段新增能力为可选分支，不影响旧路径）。

### 迁移与回滚

- 迁移步骤（如有）：
  - 需要训练导出时：在 dataset.yaml 增加 `training_output_root` 与 `pipelines`，并通过 `--qa-config` 或 `global.yaml.qa_config` 指定全局 QA 配置。
- 回滚步骤：
  - 移除 dataset.yaml 的 `pipelines`（或将 `ensure_qa/export_training` 置为 false）即可回到仅 metadata 写出路径。

