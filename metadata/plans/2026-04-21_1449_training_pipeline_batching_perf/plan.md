## 执行计划（Plan）：training_pipeline_batching_perf

### 交付物清单

- 文档：
  - `metadata/plans/2026-04-21_1449_training_pipeline_batching_perf/design.md`
  - `metadata/plans/2026-04-21_1449_training_pipeline_batching_perf/plan.md`
  - `metadata/plans/2026-04-21_1449_training_pipeline_batching_perf/test_plan.md`
  - `metadata/plans/2026-04-21_1449_training_pipeline_batching_perf/change_log.md`
- 代码：
  - `metadata/src/openspatial_metadata/cli.py`
  - `metadata/tests/test_training_pipeline_batching_perf.py`（新增）
- 配置：无
- 样例/fixtures：无

### 文档同步（与本变更一并交付）

- [ ] `metadata/docs/config_yaml_zh.md`
- [ ] `metadata/docs/metadata_spec_v0_zh.md`
- [ ] `metadata/README.md`
- [x] `metadata/plans/<本次目录>/test_plan.md`
- [x] `metadata/docs/project_progress_zh.md`（整轮结束后更新）
- [x] 其他：`无`（行为语义不变，属于性能实现细节）

### 任务拆解

1. **先补测试看护**
   - 目标：覆盖 training pipeline 中 batch 持久化/checkpoint 与 `persist_noqa=false` 冗余 dump 场景。
   - 文件：`tests/test_training_pipeline_batching_perf.py`
   - 完成条件：新增测试在改造前失败（或不通过），改造后通过。

2. **实现 batch 化持久化**
   - 目标：training pipeline 采纳 `batch_size`，减少 per-record IO。
   - 文件：`src/openspatial_metadata/cli.py`
   - 完成条件：写入与 checkpoint 改为按 batch flush。

3. **去除无效 dump**
   - 目标：`persist_noqa=false` 时避免 `md_noqa` 早 dump。
   - 文件：`src/openspatial_metadata/cli.py`
   - 完成条件：测试验证 `_md_dump` 调用减少。

### 里程碑与回滚

- 里程碑：
  - M1：测试新增并覆盖关键行为；
  - M2：实现改造完成且目标测试通过；
  - M3：全量测试通过并完成文档收束。
- 回滚策略：
  - 回滚 `cli.py` 与新增测试文件，重跑原有回归集验证恢复。
