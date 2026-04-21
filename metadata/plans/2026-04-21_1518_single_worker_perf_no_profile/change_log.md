## 变更摘要

本轮按“固定开销优先”完成了单 worker 性能优化批次，覆盖早短路与 ensure_qa 序列化链路去冗余，未改变 pipeline 模块边界与产物 schema。

## 代码变更

1. `metadata/src/openspatial_metadata/utils/pydantic_compat.py`
   - 新增 `model_copy_update_compat(model, update=...)`，统一 Pydantic v1/v2 下的 model copy/update。

2. `metadata/src/openspatial_metadata/cli.py`
   - `ensure_qa` 路径改为：
     - `build_qa_items(...)` 后直接 `model_copy_update_compat(..., {"qa_items": items})`
     - 删除中间 `md_dump -> 注入 qa_items -> md_validate` 回路。
   - 仅在 `items` 非空时构建 `md_qa` 副本，避免无意义对象重建。

3. `metadata/src/openspatial_metadata/config/qa_tasks.py`
   - 增加 `spatial_relation_2d` 任务前置可执行性检查：
     - `objects/relations` 为空直接返回 `[]`
     - `sub_tasks` 总需求 <= 0 直接返回 `[]`

4. `metadata/src/openspatial_metadata/qa/spatial_relation_2d.py`
   - 在 `generate_spatial_relation_2d_qa_items` 增加更早 guard：
     - `objects` 为空返回 `[]`
     - `relations` 为空返回 `[]`
     - `sub_tasks` 全 0 返回 `[]`
   - 复用前置计算出的 `requested`，减少重复路径开销。

## 测试变更

1. `metadata/tests/test_training_pipeline_batching_perf.py`
   - 修正 dump 统计对象为 `_md_dump_timed`（与当前实现一致）。
   - 新增用例：`ensure_qa` 生成 qa_items 时，不再触发额外中间 dump（仅保留最终落盘 dump）。

2. `metadata/tests/test_qa_spatial_relation_2d.py`
   - 新增早返回测试：
     - 缺 `objects` / 缺 `relations` 时返回空；
     - `sub_tasks` 全 0 时返回空。

3. `metadata/tests/test_qa_tasks_registry.py`
   - 新增 task 级前置短路测试：`sub_tasks` 全 0 时 `build_qa_items` 直接空列表。

## 自测记录

- `python -m pytest metadata/tests/test_training_pipeline_batching_perf.py -q` ✅
- `python -m pytest metadata/tests/test_qa_tasks_registry.py -q` ✅
- `python -m pytest metadata/tests/test_qa_spatial_relation_2d.py -q` ✅

> 备注：存在既有 Pydantic v2 deprecation warnings（历史问题），本轮未新增错误。

## 结果

- 预期效果：减少每条记录在 `ensure_qa` 中的固定序列化/校验成本，并在无法产出 QA 的样本上更早退出。
- 行为边界：不改变现有 pipeline 拓扑与输出字段语义，仅降低无效路径开销。
