## 执行计划（Plan）：prompt_templates 重构

### 目标回顾

- 将 `openspatial_metadata.qa.spatial_relation_2d` 内的 **prompt 模板**与 **response/答案模板**抽离到 `openspatial_metadata.prompt_templates` 包。
- QA 逻辑侧只保留变量抽取、采样与组装；不再硬编码文案。
- 先做 **等价迁移**，不引入新的 prompt 多样性内容改动。

### 具体改动

1. **新增包与模块**
   - 新增 `metadata/src/openspatial_metadata/prompt_templates/__init__.py`
   - 新增 `metadata/src/openspatial_metadata/prompt_templates/spatial_relation_2d.py`

2. **迁移模板内容**
   - 将以下内容从 `qa/spatial_relation_2d.py` 迁移到模板模块：
     - `FULL_SENTENCE_QUESTION_TEMPLATES`
     - `SINGLE_AXIS_QUESTION_TEMPLATES`
     - `JUDGMENT_QUESTION_TEMPLATES`
     - `FULL_SENTENCE` / `SINGLE_AXIS` / `JUDGMENT` 相关的人类可读文案（例如 answer 的句式、judgment 的固定前缀）
     - 与“标框引用文本”相关的固定句式（如 “the object in the {color} box …”）

3. **在 QA 生成逻辑中接线**
   - `qa/spatial_relation_2d.py`：
     - 移除上述模板常量与硬编码文案
     - 通过 `from openspatial_metadata.prompt_templates import spatial_relation_2d as tpl` 调用：
       - `tpl.render_full_sentence_question(...) / tpl.render_full_sentence_answer(...)`
       - `tpl.render_single_axis_question(...) / tpl.render_single_axis_answer(...)`
       - `tpl.render_judgment_question(...) / tpl.render_judgment_answer(...)`
       - `tpl.render_marked_ref(...)`（如需要）

4. **回归与整理**
   - 更新/新增最小单测（若必要）以保证模板模块可 import，并且 `generate_spatial_relation_2d_qa_items()` 输出结构不变。
   - 运行 `metadata/` 下 `pytest` 全量。

### 完成标准

- `openspatial_metadata.prompt_templates` 存在且可被 import。
- `openspatial_metadata.qa.spatial_relation_2d` 不再包含大段 prompt/answer 文案常量。
- `python -m pytest -q`（在 `metadata/` 下）通过。

