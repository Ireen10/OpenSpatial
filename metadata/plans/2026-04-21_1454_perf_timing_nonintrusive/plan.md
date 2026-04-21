## 执行计划（Plan）：perf_timing_nonintrusive

### 交付物清单

- 文档：design/plan/test_plan/change_log
- 代码：
  - `metadata/src/openspatial_metadata/cli.py`
  - `metadata/tests/test_cli_phase_timing.py`

### 任务拆解

1. 增加 phase 埋点（checkpoint/dump/persist 子项）。
2. 补测试验证 phase 统计存在且不影响既有行为。
3. 跑相关回归与全量测试。
