## 变更记录（Change Log）

### 变更摘要

- 本次新增/变更：
  - `cli.py`：`_process_jsonl_file_training_pipeline` 新增 `batch_size` 参数，并将 training pipeline 的持久化与 checkpoint 改为按 batch flush（替代逐条写/逐条 checkpoint）。
  - `cli.py`：在 training pipeline 中延后 payload dump 时机，`persist_noqa=false` 时不再为 `noqa` 生成冗余 dump。
  - `cli.py`：`_process_jsonl_files_training_parallel` 与 `main()` 调用链补齐 `batch_size` 透传。
  - 新增测试 `tests/test_training_pipeline_batching_perf.py`，看护两项行为：
    - checkpoint 次数按 batch 边界触发；
    - `persist_noqa=false` 且无 QA 输出时不触发 `_md_dump`。
- 影响范围：
  - training pipeline 的 IO 策略优化；输出语义保持不变。

### 文档与对外说明

- 已更新的文档：
  - `metadata/docs/config_yaml_zh.md`（`batch_size` 说明扩展到 training pipeline 路径）
  - `metadata/docs/project_progress_zh.md`
  - 本计划目录文档（design/plan/test_plan/change_log）

### 与上一版差异

- 变更点列表：
  - training pipeline 从“每记录 flush/checkpoint”改为“批量 flush/checkpoint”。
  - 消除 `persist_noqa=false` 分支的无效序列化。
- 删除/废弃点：
  - 无对外功能废弃。

### 迁移与回滚

- 迁移步骤：
  - 无需迁移。
- 回滚步骤：
  - 回滚 `cli.py` 与新增测试文件并重跑回归。

### 自测结果

- `python -m pytest -q tests/test_training_pipeline_batching_perf.py tests/test_training_pipeline_cli_e2e.py tests/test_records_parallelism_order.py`
  - 结果：`8 passed`
- `python -m pytest -q`
  - 结果：`115 passed`
