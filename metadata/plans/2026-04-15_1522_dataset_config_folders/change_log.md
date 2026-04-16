## 变更记录（Change Log）：datasets 配置文件夹化（2026-04-15）

### 变更摘要

- **配置组织**：`metadata/configs/datasets/` 改为 **一数据集一文件夹**：
  - `<dataset_name>/dataset.yaml`（唯一被发现/加载的配置文件）
  - `<dataset_name>/README.md`（记录数据结构与 mapping，便于 adapter 开发）
- **不再兼容平铺 YAML**：删除 `metadata/configs/datasets/demo_dataset.yaml`，迁移为 `metadata/configs/datasets/demo_dataset/dataset.yaml`
- **loader**：`discover_dataset_configs` 仅发现 `*/dataset.yaml`；`load_dataset_config` 支持传目录（自动读取 `dataset.yaml`）
- **测试**：更新 `metadata/tests/test_framework_unittest.py` 中 demo 配置路径

### 自测

- `python -m pytest metadata/tests -q`
  - 结果：29 passed

