## 执行计划：dataset output_root

### 代码修改

- `metadata/src/openspatial_metadata/cli.py`
  - 将 `output_root` 的选择从“全局一次”改为“按 dataset 一次”
  - 读取 `ds.output_root`（若存在）并应用优先级规则
  - 将 `output_root` 传递到处理函数（用于写文件与 checkpoints）

### 测试

- 新增 `metadata/tests/test_cli_dataset_output_root.py`
  - 构造两个 dataset config（不同 `output_root`）
  - 同一次 `main()` 运行，断言输出分别落在各自目录

### 自测

- `python -m pytest metadata/tests -q`

### 完成后

- 写 `change_log.md`
- 提交并推送

