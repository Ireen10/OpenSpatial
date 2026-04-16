## 变更记录（Change Log）：dataset enrich 配置 + CLI 执行（2026-04-15）

### 变更摘要

- **配置**：dataset `dataset.yaml` 支持新增 `enrich` 块：
  - `enrich.relations_2d: bool`
  - `enrich.relations_3d: bool`（本次仅落配置，执行时报未实现）
- **CLI**：`openspatial_metadata.cli` 在写出前按开关执行 `enrich_relations_2d`
  - enrich 前后保持 `aux.record_ref`
- **demo 配置**：`demo_dataset/dataset.yaml` 显式关闭 enrich
- **测试**：新增 `metadata/tests/test_cli_enrich_config.py` 覆盖开关与 `aux.enrich_2d` 写入

### 自测

- `python -m pytest metadata/tests -q`
  - 结果：39 passed

