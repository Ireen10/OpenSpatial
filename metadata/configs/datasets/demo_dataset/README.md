# demo_dataset

该目录演示 **一数据集一文件夹** 的配置组织方式：

- `dataset.yaml`：数据集配置（供 `openspatial-metadata` CLI 发现与加载）
- `README.md`：该数据集的结构说明/字段映射/已知坑（供后续 adapter 开发）

## 输入数据

本 demo 仅用于框架测试，输入来自：

- `metadata/tests/fixtures/jsonl_shard_small.jsonl`（`input_type: jsonl`）
- `metadata/tests/fixtures/json_files_small/*.json`（`input_type: json_files`）

## adapter

使用 `PassthroughAdapter`，主要验证：

- 配置发现（`datasets/*/dataset.yaml`）
- CLI 读取配置并产出 JSON/JSONL
- 输出目录组织与 checkpoint

