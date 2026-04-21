## 执行计划（Plan）：resume_perf_tqdm_stability

### 交付物清单

- 文档：design / plan / test_plan / change_log
- 代码：
  - `metadata/src/openspatial_metadata/io/json.py`
  - `metadata/src/openspatial_metadata/cli.py`
  - `metadata/tests/test_io_json_resume_skip.py`（新增）

### 任务拆解

1. 先补测试：验证 `iter_jsonl(start_index=...)` 不解析被跳过行。
2. 修改 `iter_jsonl` 与 CLI 调用链，resume 直传 `start_index`。
3. 调整 `tqdm` 模式下并行 done 日志写入策略。
4. 跑回归和全量测试，更新文档收束。
