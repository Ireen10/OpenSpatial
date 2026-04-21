## 变更记录（Change Log）

### 变更摘要

- 本次新增/变更：
  - `io/json.py`：`iter_jsonl` 增加 `start_index`，跳过区间不再执行 `json.loads`。
  - `cli.py`：resume 路径改为 `iter_jsonl(..., start_index=next_idx)`，移除循环内重复的 `input_index` 过滤。
  - `cli.py`：`progress=tqdm` 下抑制并行 worker 高频 done 日志，减少 `tqdm.write` 干扰。
  - 新增测试 `tests/test_io_json_resume_skip.py` 验证跳过区间不解析 JSON。
- 影响范围：
  - 续跑阶段启动/跳过性能提升；
  - tqdm 多进度条控制台布局更稳定；
  - 输出语义与处理顺序不变。

### 文档与对外说明

- 已更新：
  - `metadata/plans/2026-04-21_1503_resume_perf_tqdm_stability/design.md`
  - `metadata/plans/2026-04-21_1503_resume_perf_tqdm_stability/plan.md`
  - `metadata/plans/2026-04-21_1503_resume_perf_tqdm_stability/test_plan.md`
  - `metadata/plans/2026-04-21_1503_resume_perf_tqdm_stability/change_log.md`
  - `metadata/docs/project_progress_zh.md`

### 自测结果

- 目标回归：
  - `python -m pytest -q tests/test_io_json_resume_skip.py tests/test_records_parallelism_order.py tests/test_parallel_cli.py tests/test_training_pipeline_cli_e2e.py`
  - 结果：`12 passed`
- metadata 全量：
  - `python -m pytest -q`
  - 结果：`117 passed`
