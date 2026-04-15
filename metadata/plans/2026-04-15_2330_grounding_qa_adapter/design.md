## 设计：`GroundingQAAdapter`（RefCOCO grounding-aug 对话 JSONL → MetadataV0）

### 背景

数据集 `refcoco_grounding_aug_en_250618` 的样本以 **多轮对话 JSONL** 表达，并将 grounding（ref_exp + bbox）编码在 assistant 的文本中：

- `<|object_ref_start|>...<|object_ref_end|>`：指代表达（ref_exp）
- `<|box_start|>(x1,y1),(x2,y2)<|box_end|>`：归一化到 0~1000 的 bbox（xyxy），一个 ref 可跟多个 box

需要一个 adapter 将每行 record 转成项目统一的 `MetadataV0`：

- `sample.image.path/width/height/coord_*`
- `objects[]`：展开 bbox 为对象
- `queries[]`：用 ref_exp 表达 query，指向 candidate objects（多 bbox）

### 目标

- 新增 `GroundingQAAdapter`（或同义命名）用于：
  - 解析 user content 中 image（`relative_path/width/height`）
  - 解析 assistant content 中 grounding 标记并展开 object/query
  - 对异常/缺失情况有清晰的跳过策略（不崩溃）
- 与现有 CLI 适配：遵循 adapter 的 `convert(record: Dict) -> Dict` 协议

### 非目标

- 不在 adapter 内生成 `relations`（关系增强由 enrich 阶段完成）
- 不在 adapter 内做复杂的清洗/纠错（如 bbox 裁剪、NMS），除非必要

### 输入结构（抽象）

单条 record（简化）：

- `id: str`
- `data: list[{role: "user"|"assistant", content: list[...]}]`
- `content` 元素为：
  - text：`{"type":"text","text":{"string": ...}}`
  - image：`{"type":"image","image":{"relative_path":..., "width":..., "height":...}}`

grounding 信息在 assistant 的 text 中（可能多轮、多 ref、多 box）。

### 输出结构（最小）

输出 `dict` 形状满足 `MetadataV0.parse_obj`：

- `dataset`: `{name, version, split?, ...}`
- `sample`: `{sample_id, view_id, image:{path,width,height,coord_space,coord_scale}}`
- `objects`: `[{object_id, category, phrase?, bbox_xyxy_norm_1000, quality?}, ...]`
- `queries`: `[{query_id, query_text, query_type?, candidate_object_ids, gold_object_id?, count?, filters?}, ...]`
- `relations`: `[]`
- `aux`: `{...}`

### 解析策略与规则

#### 1) image 抽取

- 从 `data` 中第一个出现的 `content.type=="image"` 读取：
  - `relative_path` → `sample.image.path`
  - `width/height` → `sample.image.width/height`
- 若找不到 image：
  - `sample.image.path` 置空字符串或占位（建议：记录到 `aux.adapter_warnings` 并跳过该 record，取决于 strict 模式）

#### 2) query 抽取（ref_exp）

- 遍历每条 assistant message 的 text，提取多个 `ref_exp`
- 对每个 `ref_exp`，解析其后紧跟的一个或多个 `<|box_start|>...<|box_end|>` 块
- 跳过规则（与数据说明一致）：
  - 只有 ref 没有 box：跳过该 ref
  - 只有 box 没有 ref：跳过该 box 块

#### 3) bbox 解析

- bbox 文本形态：`(ddd,ddd),(ddd,ddd)`，允许空格
- 输出为 `bbox_xyxy_norm_1000=[x1,y1,x2,y2]`（int）
- 不做裁剪；若出现 x1>=x2 或 y1>=y2 则丢弃该 bbox 并记录 warning（object 级过滤也会再处理）

#### 4) objects / queries 展开与 id 约定

- 每个 bbox 展开为一个 `ObjectV0`
  - `object_id`：使用 `MetadataV0.make_object_id("obj", running_index)` 或 `f"obj#{i}"`
  - `category`：可统一填 `"object"` 或 `"refcoco_obj"`（保持稳定即可）
  - `phrase`：可选填 ref_exp（但不强制；多 ref 指向同 object 不常见于本数据）
- 每个 ref_exp 生成一个 `QueryV0`
  - `query_id`：`MetadataV0.make_query_id("q", running_index)` 或 `f"q{i}"`
  - `query_text`：ref_exp
  - `candidate_object_ids`：该 ref_exp 对应的 objects
  - `count`：bbox 个数
  - `gold_object_id`：仅当 bbox 个数 == 1 时填该 object_id（可选）

### 错误处理与可观测性

- 在 `aux` 下记录：
  - `aux.adapter_name = "GroundingQAAdapter"`
  - `aux.adapter_warnings: list[...]`：image 缺失、解析失败、bbox 非法等
  - `aux.adapter_stats: {...}`：解析到的 ref 数、bbox 数、objects/queries 数

### 测试设计（概览）

- 用 README 的真实样例裁剪出最小 fixture（或直接在 UT 内写一个 record dict）：
  - 1 张 image + 2 轮 query/answer，每轮 1 个 ref + 1 个 box
  - 断言：
    - image path/size 解析正确
    - `queries` 数量与 `objects` 数量匹配
    - object bbox 数值正确
    - `relations` 为空

