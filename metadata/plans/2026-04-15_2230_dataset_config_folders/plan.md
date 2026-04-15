## 执行计划：datasets 配置改为“一数据集一文件夹”

### 范围

- **配置迁移**
  - 迁移 `metadata/configs/datasets/demo_dataset.yaml` → `metadata/configs/datasets/demo_dataset/dataset.yaml`
  - 新增 `metadata/configs/datasets/demo_dataset/README.md`（示例说明）
- **代码修改**
  - `openspatial_metadata.config.loader`：
    - `discover_dataset_configs`：只发现 `*/dataset.yaml`
    - `load_dataset_config`：支持传目录（自动补 `dataset.yaml`）与传 `dataset.yaml` 文件
  - 若 CLI 或其它模块对路径/发现逻辑有假设，则同步更新
- **测试修改**
  - 更新 `metadata/tests/test_framework_unittest.py::test_config_loader_discovers_demo`
    - 断言发现的是 `demo_dataset/dataset.yaml`
    - `load_dataset_config` 入参改为新路径（或目录）
- **文档**
  - 本次主要是 datasets 配置的组织方式；无需改 metadata schema 文档

### 实施步骤

1. **梳理现状与调用点**
   - 搜索 `discover_dataset_configs(`、`load_dataset_config(` 的调用位置
   - 搜索硬编码路径 `metadata/configs/datasets/*.yaml` 的使用点（若有）

2. **修改 loader（仅支持文件夹结构）**
   - `discover_dataset_configs(root: Path)`：
     - 返回 `sorted([p.as_posix() for p in root.glob("*/dataset.yaml")])`
   - `load_dataset_config(path: str | Path)`：
     - 若传入的是目录：读取 `<dir>/dataset.yaml`
     - 若传入的是文件：直接读
     - 若传入的是旧平铺 `*.yaml`（root 下直接文件）：抛出清晰错误（提示迁移）

3. **迁移 demo 配置并补 README**
   - 移动/重建文件到新目录：
     - `metadata/configs/datasets/demo_dataset/dataset.yaml`
     - `metadata/configs/datasets/demo_dataset/README.md`
   - README 内容建议包含：
     - 输入文件格式（jsonl/json/…）
     - 关键字段与到 `MetadataV0` 的映射
     - 已知数据坑与处理策略
     - 最小样例（可选，脱敏）

4. **更新测试**
   - 修改 `test_config_loader_discovers_demo`：
     - 断言发现路径包含 `demo_dataset/dataset.yaml`
     - `load_dataset_config` 传入新路径（或目录）

5. **自测**
   - `python -m pytest metadata/tests -q`

6. **变更记录**
   - 实施完成后补 `change_log.md`（记录破坏性变更、迁移点、测试结果）

### 完成标准

- `metadata/configs/datasets/` 下不再存在平铺的 `*.yaml` 数据集配置
- `discover_dataset_configs` 只返回 `*/dataset.yaml`
- demo + CLI + 单测可用：`pytest metadata/tests -q` 全绿

