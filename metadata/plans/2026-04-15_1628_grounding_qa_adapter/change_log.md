## 变更记录（Change Log）：`GroundingQAAdapter`（2026-04-15）

### 变更摘要

- **新增**：`openspatial_metadata.adapters.grounding_qa.GroundingQAAdapter`
  - 解析多轮对话 JSONL 中 assistant 的 grounding 标记（ref + bbox）
  - 产出 `MetadataV0` 形状的 dict（objects + queries；relations 为空）
- **CLI 集成**：`openspatial_metadata.cli` 现会根据 dataset config 的 `adapter` 实例化并调用 `convert(record)`
  - 保持输出始终带 `aux.record_ref`（输入文件与行号）
- **测试**：新增 `metadata/tests/test_adapter_grounding_qa.py`

### 自测

- `python -m pytest metadata/tests -q`
  - 结果：31 passed

