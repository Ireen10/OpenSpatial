## 测试计划：`queries` schema 落地

### 目标

验证 `MetadataV0.queries` 的**向后兼容**与**roundtrip**，并确保不影响现有测试集。

### 测试项

- **UT-Q1（向后兼容）**：旧 JSON（不含 `queries`）可被 `MetadataV0.parse_obj`（或 `parse_raw`）解析，且 `queries == []`
- **UT-Q2（roundtrip）**：带 `queries` 的 JSON 解析后，`dict()`/`json()` 输出保留关键字段：
  - `queries[0].query_id`
  - `queries[0].candidate_object_ids`
  - `queries[0].gold_object_id`
  - `queries[0].count`

### 执行命令

- `python -m pytest metadata/tests -q`

### 通过标准

- 所有测试通过
- UT-Q1/UT-Q2 均覆盖到新增字段

