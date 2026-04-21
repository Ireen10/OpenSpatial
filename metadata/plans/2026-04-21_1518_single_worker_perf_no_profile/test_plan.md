## 测试计划

本测试计划与 `plan.md` 一一对应，优先覆盖“早短路正确性”和“冗余序列化移除”两类风险点。

### T1 - spatial_relation_2d 早短路

- 目标功能点：P0-1（生成入口早返回）
- 用例：
  1. `objects=[]` 且 `relations` 非空 -> 返回 `[]`
  2. `relations=[]` 且 `objects` 非空 -> 返回 `[]`
  3. `sub_tasks` 全 0 -> 返回 `[]`
- 期望：无异常、输出为空、与旧行为语义一致（只是更早退出）。

### T2 - task 级最小条件检查

- 目标功能点：P0-1（`build_qa_items` 前置校验）
- 用例：
  1. `qa_task_name=spatial_relation_2d` 且 metadata 缺少必要输入 -> 直接空列表
  2. 正常 metadata -> 仍能生成 qa_items
- 期望：仅在“无法生成”的样本触发短路，不影响可生成样本。

### T3 - ensure_qa 冗余 dump/validate 收敛

- 目标功能点：P0-2（`md_dump + md_validate` 替换为 model copy/update）
- 用例：
  1. monkeypatch 统计 `_md_dump_timed` 调用次数，执行 `enable_ensure_qa=true` 且生成 qa_items 的路径
  2. 确认较改造前减少至少一次中间 dump
- 期望：最终输出结构不变，调用次数下降。

### T4 - 已有回归套件

- 目标功能点：P1-1/P1-2（无回退）
- 执行：
  - `metadata/tests/test_training_pipeline_batching_perf.py`
  - `metadata/tests/test_io_json_resume_skip.py`
  - `metadata/tests/test_qa_tasks_registry.py`
  - `metadata/tests/test_qa_spatial_relation_2d.py`
- 期望：全部通过，确认 batching/resume/qa 主行为保持稳定。
