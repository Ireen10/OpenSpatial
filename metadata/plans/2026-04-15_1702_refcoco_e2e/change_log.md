## 变更记录（Change Log）：RefCOCO grounding 最小 E2E（2026-04-15）

### 变更摘要

- **数据集配置**：新增 `refcoco_grounding_aug_en_250618/dataset.yaml`，配置 GroundingQAAdapter 并开启 `enrich.relations_2d`
- **样例输入**：新增 `sample_small.jsonl`（单条真实 record），用于本地/CI 端到端验证
- **global.yaml 生效**：CLI 实例化 adapter 时注入 `coord_scale=global.scale` 与 `split=split.name`
- **测试**：新增 `test_cli_e2e_refcoco_small.py` 覆盖 config→read→convert→enrich→write 以及 scale 注入

### 自测

- `python -m pytest metadata/tests -q`
  - 结果：40 passed

