## 设计：在 v0 metadata 中引入 `queries`

### 背景与问题

当前代码落地的 v0 schema（`openspatial_metadata.schema.metadata_v0`）仅包含 `dataset/sample/objects/relations/aux`。  
但在 grounding/指代任务中，“一个指代表达（文本）对应一个物体或多个物体”的信息需要被显式建模，否则会出现：

- 同一句表达需要复制到多个 `ObjectV0.phrase` 上（语义不清、难以审计）
- 无法表达“一个 query 本来就指向一个集合（set）”的监督信号
- 很难做一致性校验（如上游 `count` 与候选集合大小）

规范文档 `metadata_spec_v0_zh.md` 已定义 `queries: list[Query]`（可为空），但 wiki 与当前 schema 尚未落地。

### 目标

- **在 schema 中增加 `QueryV0` 与 `MetadataV0.queries`**，用于承载指代/grounding 查询：
  - 支持表达 **单实例 vs 多实例**（通过 `candidate_object_ids` / `gold_object_id` / `count`）
  - 允许为空，不影响仅消费 `objects/relations` 的流程
- **更新 wiki 文档**：让团队归档 JSON 结构包含 `queries`（可选），并提供字段字典与示例
- **保持向后兼容**：
  - 旧 JSON（无 `queries` 字段）应可被解析，默认 `queries=[]`
  - 现有 enrich/关系计算不依赖 `queries`，不应被破坏

### 非目标

- 不在本次引入复杂的 query 过滤/空间词识别等派生逻辑（可在后续 enrichment 或 QA 生产阶段加入）
- 不强制所有数据必须提供 `queries`

### 数据结构（最小集合）

新增 `QueryV0`（允许 extra 字段）：

- `query_id: str`
- `query_text: str`
- `query_type: Optional[str] = None`（与 spec 对齐，但不强制枚举）
- `candidate_object_ids: List[str] = []`
- `gold_object_id: Optional[str] = None`
- `count: Optional[int] = None`
- `filters: Dict[str, Any] = {}`（可选，留给 contains_spatial_terms 等）

并在 `MetadataV0` 增加：

- `queries: List[QueryV0] = []`

### 与文档的一致性策略

- `metadata_spec_v0_zh.md` 已包含 `Query` 段落，本次不改变其核心语义，仅在必要时补充“与当前代码 schema 的字段命名对应关系/说明”
- `metadata_wiki_v0_zh.md` 补齐：
  - 顶层 JSON 示例中加入 `queries`
  - 顶层字段总览表加入 `queries`
  - 数据字典加入 `queries[]` 说明（可直接引用/对齐 spec 的字段）

### 风险与兼容性

- **Schema 变化**：新增字段与模型，属于向后兼容扩展；对已有消费者影响极低
- **测试**：补充单测覆盖“缺省 queries”“带 queries 的 roundtrip”

