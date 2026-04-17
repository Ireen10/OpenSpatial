## 设计（Design）：将 QA prompt/response 模板抽离为 `prompt_templates` 包

### 背景

当前 `spatial_relation_2d` 的 QA 生成在 `metadata/src/openspatial_metadata/qa/spatial_relation_2d.py` 内部直接硬编码了：

- prompt 模板（用于构造用户侧/系统侧提示词）
- response/答案的文本模板（用于构造 assistant 输出）

这会导致：

- **难以迭代**：prompt 多样性设计需要频繁修改 Python 逻辑文件，review/回滚成本高。
- **耦合过强**：采样逻辑（“怎么选模板/怎么填变量”）与文案（“模板是什么”）混在一起。
- **复用困难**：未来新增任务（2D/3D/其它 QA）时无法形成统一的模板管理入口。

目标是像 OpenSpatial 主工程那样：用一个专门的包来管理各任务模板，使后续 prompt 设计能在模板文件中独立进行。

### 目标（本轮要交付）

1. **新增模板包**：引入 `openspatial_metadata.prompt_templates`（Python package）。
2. **模板外置**：
   - 将 `spatial_relation_2d` 的 prompt 模板迁移到 `prompt_templates/spatial_relation_2d.py`（或同名模块）。
   - 将 `spatial_relation_2d` 的 response/答案模板也迁移到同一处（或拆分为 `*_responses.py`）。
3. **代码解耦**：`openspatial_metadata.qa.spatial_relation_2d` 仅保留：
   - 任务配置解析、采样/组装逻辑
   - 对模板模块的调用（选择模板、format 填充）
   - **不再**硬编码任何中文/英文 prompt 文案与答案模板文本。
4. **行为不变（先等价迁移）**：重构后生成的 `qa_items` 内容在不改模板的前提下应保持一致或等价（允许极少量格式差异，但不改变结构字段与语义）。

### 非目标（本轮不做）

- 不做 prompt 多样性“设计内容升级”（那是你后续要专注的部分）。
- 不引入新的 QA task 或新的 schema 字段。
- 不做 YAML 里模板版本管理/热加载（先保持 Python 包内模板常量方式）。

### 设计方案

#### 目录结构

新增：

- `metadata/src/openspatial_metadata/prompt_templates/__init__.py`
- `metadata/src/openspatial_metadata/prompt_templates/spatial_relation_2d.py`

其中 `spatial_relation_2d.py` 只负责提供模板常量与轻量 helper（如统一的 `render_*()`，可选）。

#### 模板表达形式

优先保持“等价迁移、低风险”：

- 使用 Python 常量（`str` / `dict` / `list`）保存模板文本与分组
- QA 生成侧通过模板名 key 选择、再 `.format(...)` 或 f-string 风格填充

后续你需要做多样性设计时，只改 `prompt_templates/spatial_relation_2d.py` 的模板集合与权重/分组即可，不需要碰 QA 逻辑。

#### 代码边界

- `qa/spatial_relation_2d.py`：
  - 只做：从 metadata 中抽取变量 → 选择模板 → 调用模板渲染 → 组装 `AnnotationQaItemV0`
- `prompt_templates/spatial_relation_2d.py`：
  - 只放：模板文本、模板分组、（可选）渲染函数

### 兼容性与回归风险

- **接口兼容**：`generate_spatial_relation_2d_qa_items()` 的输入/输出不变。
- **最小改动原则**：先把原有模板文本原封不动挪走；确保测试全绿后，再开始模板多样性迭代。

