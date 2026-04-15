## 变更记录（Change Log）：dataset 输出目录配置（2026-04-15）

### 变更摘要

- **dataset.yaml 支持 `output_root`**：每个数据集可指定其输出根目录
- **优先级**：`--output-root`（最高）→ `dataset.output_root` → `global.yaml.output_root`
- **测试**：新增 `test_cli_dataset_output_root.py` 验证同次运行多个数据集写入不同目录

### 自测

- `python -m pytest metadata/tests -q`
  - 结果：41 passed

