## 测试计划：datasets 配置改为“一数据集一文件夹”

### 目标

验证新目录结构（`metadata/configs/datasets/<name>/dataset.yaml`）在 discover/load/CLI 路径下可用，并确保不再依赖平铺 YAML。

### 测试项

- **UT-D1（discover）**：`discover_dataset_configs("metadata/configs/datasets")` 能发现 `demo_dataset/dataset.yaml`
- **UT-D2（load）**：
  - 传入 `.../demo_dataset/dataset.yaml` 可加载
  - 传入 `.../demo_dataset/`（目录）可加载（内部自动补 `dataset.yaml`）
- **UT-D3（CLI smoke）**：`TestFramework.test_cli_io` 仍能运行成功（其 `--config-root` 指向 demo 配置的新路径）

### 执行命令

- `python -m pytest metadata/tests -q`

### 通过标准

- 全部测试通过
- repo 中不再存在 `metadata/configs/datasets/*.yaml` 的平铺数据集配置（仅允许子目录结构）

