## 变更记录（Change Log）

### 变更摘要

- 本次新增/变更：
  - `cli.py` 增加非侵入 timing phase：
    - `checkpoint_write`
    - `metadata_dump`
    - `persist_noqa_write`
    - `persist_qa_write`
  - 埋点仅通过 `PhaseTimer` 聚合，不新增运行中日志输出，不改 `_log`/`_tqdm` 路径。
  - `tests/test_cli_phase_timing.py` 增加格式化输出断言，覆盖新增 phase 名可见性。

### 文档与对外说明

- 已更新文档：
  - `metadata/plans/2026-04-21_1454_perf_timing_nonintrusive/design.md`
  - `metadata/plans/2026-04-21_1454_perf_timing_nonintrusive/plan.md`
  - `metadata/plans/2026-04-21_1454_perf_timing_nonintrusive/test_plan.md`
  - `metadata/plans/2026-04-21_1454_perf_timing_nonintrusive/change_log.md`
  - `metadata/docs/project_progress_zh.md`

### 自测结果

- `python -m pytest -q tests/test_cli_phase_timing.py tests/test_training_pipeline_batching_perf.py tests/test_training_pipeline_cli_e2e.py`
  - 结果：`10 passed`
- `python -m pytest -q`
  - 结果：`116 passed`
