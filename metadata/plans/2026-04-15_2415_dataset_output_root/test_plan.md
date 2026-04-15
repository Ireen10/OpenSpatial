## 测试计划：dataset output_root

### 测试项

- **UT-O1：优先级**
  - 当指定 `--output-root` 时，忽略 dataset.output_root
  - 当未指定 `--output-root` 且 dataset.output_root 存在时，使用 dataset.output_root
  - 否则回退到 global.yaml.output_root

- **UT-O2：多数据集隔离输出**
  - 同次运行处理两个数据集配置，各自输出落到各自 output_root 下

### 执行命令

- `python -m pytest metadata/tests -q`

