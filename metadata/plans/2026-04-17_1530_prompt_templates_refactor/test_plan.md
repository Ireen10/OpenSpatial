## 测试计划（Test Plan）：prompt_templates 重构

### 目标

验证 prompt/response 模板抽离后：

- QA 生成流程可正常运行
- 输出 schema/关键字段不变
- 不引入 import/path 问题

### 测试项

1. **UT：模板模块可 import**
   - 在 Python 环境中 import `openspatial_metadata.prompt_templates.spatial_relation_2d` 不报错。

2. **UT：QA 生成可运行（回归）**
   - 运行现有 `metadata/tests/test_qa_spatial_relation_2d.py`（覆盖 `generate_spatial_relation_2d_qa_items`）。
   - 运行 `metadata/tests/test_qa_tasks_registry.py`（覆盖 registry → params → build_qa_items 调度链路）。

3. **全量回归**
   - 在 `metadata/` 下执行：
     - `python -m pytest -q`

### 通过标准

- 所有测试通过；无新增 lints（如有）。

