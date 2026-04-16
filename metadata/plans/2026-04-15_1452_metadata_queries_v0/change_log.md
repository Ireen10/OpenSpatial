## 变更记录（Change Log）：v0 引入 `queries`（2026-04-15）

### 变更摘要

- **Schema**：在 `openspatial_metadata.schema.metadata_v0` 新增 `QueryV0`，并为 `MetadataV0` 增加 `queries: List[QueryV0]`（默认空列表，向后兼容）。
- **Wiki**：`metadata/docs/metadata_wiki_v0_zh.md` 补齐 `queries`：
  - 顶层 JSON 示例新增 `queries`
  - 顶层字段总览与模块划分新增 `queries`
  - 数据字典新增 `queries[]` 字段说明
- **测试**：新增 `metadata/tests/test_schema_queries.py` 覆盖缺省与 roundtrip。

### 自测

- `python -m pytest metadata/tests -q`
  - 结果：29 passed

