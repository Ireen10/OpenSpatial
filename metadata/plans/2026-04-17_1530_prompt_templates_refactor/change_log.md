## Change Log：prompt_templates 重构（spatial_relation_2d）

### 本轮交付摘要

- **新增模板包**：`openspatial_metadata.prompt_templates`
  - `prompt_templates/spatial_relation_2d.py` 统一管理 `spatial_relation_2d` 的 prompt 与 answer 文案模板。
- **QA 逻辑解耦**：`openspatial_metadata.qa.spatial_relation_2d` 不再硬编码 prompt/answer 文案，改为调用模板模块的 `render_*` 函数生成 question/answer 与标框引用文本。
- **行为保持等价**：本轮仅做迁移与接线，不引入新的模板内容与采样策略改动。

### 自测

- `python -m pytest -q`（在 `metadata/` 下）：通过。

