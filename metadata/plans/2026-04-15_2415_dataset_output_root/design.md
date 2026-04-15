## 设计：dataset.yaml 配置每个数据集的输出目录（output_root）

### 背景

当前 CLI 通过 `--output-root`（或 `global.yaml.output_root`）指定统一输出根目录，并在其下按 `dataset.name/split` 分桶。

当一次运行要处理多个数据集配置时，统一输出根目录不利于：

- 不同数据集输出隔离（尤其是跨不同存储盘/挂载点）
- 不同数据集采用不同输出保留策略（清理/归档/权限）

### 目标

支持在每个数据集的 `dataset.yaml` 中指定该数据集的输出根目录：

- `output_root: <path>`

优先级（高→低）：

1. CLI 参数 `--output-root`（全局覆盖）
2. dataset.yaml 的 `output_root`
3. global.yaml 的 `output_root`

### 行为

- 每个数据集使用其最终选定的 `output_root`：
  - 输出仍为 `<output_root>/<dataset.name>/<split.name>/...`
  - checkpoints 目录仍在该 `output_root/.checkpoints/`

### 兼容性

- 不改现有参数；不写 dataset.output_root 时行为不变
- `DatasetConfig` 允许 extra 字段，因此无需改 config schema

