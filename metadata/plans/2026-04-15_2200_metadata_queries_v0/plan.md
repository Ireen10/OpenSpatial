## 执行计划：在 v0 metadata 中引入 `queries`

### 范围

- **代码**：`metadata/src/openspatial_metadata/schema/metadata_v0.py`
- **文档**：
  - `metadata/docs/metadata_wiki_v0_zh.md`（补齐 `queries`）
  - `metadata/docs/metadata_spec_v0_zh.md`（原则上不改语义；如有必要仅做“与代码落地一致”的小修订）
- **测试**：新增最小单测覆盖 schema 解析与序列化

### 具体步骤

1. **Schema 增量扩展（向后兼容）**
   - 在 `metadata_v0.py` 新增 `QueryV0(BaseModel)`，`extra = "allow"`
   - 在 `MetadataV0` 增加字段 `queries: List[QueryV0] = Field(default_factory=list)`
   - `QueryV0` 的默认字段策略：
     - `candidate_object_ids` / `filters` 使用 `default_factory`，避免共享可变默认值

2. **Wiki 文档补齐**
   - 顶层 JSON 示例加入 `queries`（可为空列表）
   - 顶层字段总览表加入 `queries` 行（可选）
   - 数据字典新增 `queries[]` 的字段说明（尽量与 spec 的 `Query` 一致）
   - 维持 wiki 的“最小骨架”定位：强调 `queries` **可选**，但推荐用于 grounding 单/多实例表达

3. **（可选）Spec 文档一致性微调**
   - 若发现 spec 的顶层字段与当前代码落地（`dataset/sample/...`）存在命名差异导致读者混淆，则仅补一段说明：
     - “规范的顶层字段” vs “代码当前 `MetadataV0` 的落地结构”
   - 不改 spec 的核心字段定义与示例语义

4. **测试**
   - 新增 `metadata/tests/test_schema_queries.py`（或等价命名）：
     - **UT-Q1**：无 `queries` 字段的旧 JSON 能 parse，且 `md.queries == []`
     - **UT-Q2**：带 `queries` 的 JSON roundtrip（parse → dict）保留关键字段

5. **自测**
   - 运行 `python -m pytest metadata/tests -q`

6. **变更记录**
   - 在本目录补 `change_log.md`：记录新增 schema 字段、文档更新点、测试结果

### 完成标准

- `MetadataV0` 支持 `queries`，且对旧数据保持兼容
- `metadata_wiki_v0_zh.md` 顶层结构与数据字典包含 `queries`
- 单测通过：`pytest metadata/tests -q`

