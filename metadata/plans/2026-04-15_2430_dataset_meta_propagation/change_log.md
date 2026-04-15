## 变更记录（Change Log）：dataset meta 注入 Metadata（2026-04-15）

### 变更摘要

- **CLI 注入**：将 `dataset.yaml` 的 `meta` 写入输出 `MetadataV0.dataset`
  - `meta.source` → `dataset.source`（若输出未提供）
  - `dataset.meta`（扩展字段）保存整段 `ds.meta`
- **测试**：
  - 新增 `test_cli_dataset_meta.py`
  - E2E refcoco 小样例新增断言 `dataset.source == local_fixture`

### 自测

- `python -m pytest metadata/tests -q`
  - 结果：42 passed

