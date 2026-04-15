## 设计：datasets 配置改为“一数据集一文件夹”

### 背景

当前 `metadata/configs/datasets/` 下以 YAML 平铺存放数据集配置。你希望每个数据集在其配置旁边放置若干 Markdown（数据结构说明、字段映射、已知坑、样例等），以便后续开发/维护 adapter。

平铺结构在以下方面不便管理：

- 配置文件名与数据集说明文档难以形成天然聚合
- 不同数据集的补充资料（样例、mapping、notes）难以归档
- 配置数量增长后目录拥挤，review/维护成本上升

### 目标

- 将数据集配置统一迁移为：
  - `metadata/configs/datasets/<dataset_name>/dataset.yaml`
  - `metadata/configs/datasets/<dataset_name>/README.md`（或其它 md）
- **不再兼容平铺 YAML**（迁移策略 B）
- 更新配置发现与加载逻辑，确保 CLI 与单测通过
- 提供一个示例（用现有 demo 数据集）展示 `README.md` 写法

### 非目标

- 不在本次强制规定 README 的模板内容（仅给建议结构与示例）
- 不引入新的配置格式（仍使用 YAML）

### 约定与行为

#### 目录约定

- 数据集目录名使用 `dataset.name`（或与其一致的安全文件名）
- 主配置固定命名为 `dataset.yaml`

#### loader 行为（新的唯一来源）

- `discover_dataset_configs(root)` 只发现 `root/*/dataset.yaml`
- `load_dataset_config(path_or_name)` 支持：
  - 直接传入 `.../<dataset_name>/dataset.yaml`
  - 或传入 dataset 目录（`.../<dataset_name>/`）时自动读取其中 `dataset.yaml`
- 若 root 下存在平铺 `*.yaml`，视为非法/忽略（本次不兼容）

### 风险与迁移

- **破坏性变更**：任何依赖平铺 YAML 路径的脚本会受影响，需要同步更新调用路径
- 通过更新 CLI/测试覆盖与提供 demo 目录示例降低迁移风险

