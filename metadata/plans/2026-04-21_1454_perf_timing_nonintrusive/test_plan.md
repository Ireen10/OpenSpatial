## 测试方案（Test Plan）：perf_timing_nonintrusive

### 测试范围

- 新增 phase 聚合是否生效；
- 既有 CLI 进度与执行行为不回归（通过现有测试保障）。

### 单元测试

- `tests/test_cli_phase_timing.py`（新增 format 侧断言）
- `tests/test_training_pipeline_batching_perf.py`
- `tests/test_training_pipeline_cli_e2e.py`

### 质量门槛

- 相关测试与 metadata 全量测试通过；
- 不新增运行时日志输出逻辑。
