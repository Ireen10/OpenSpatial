## 测试方案（Test Plan）：resume_perf_tqdm_stability

### 测试范围

- resume 跳过阶段性能优化的正确性；
- tqdm 模式行为不回归（进度条主路径稳定）。

### 单元测试

- 新增：`tests/test_io_json_resume_skip.py`
  - 断言 `start_index` 前行不会触发 `json.loads`。
- 回归：
  - `tests/test_records_parallelism_order.py`
  - `tests/test_parallel_cli.py`
  - `tests/test_training_pipeline_cli_e2e.py`

### 质量门槛

- 相关测试与 metadata 全量测试通过；
- 不新增运行时日志噪音。
