## Change log

### Summary

- **Checkpoint 目录改为按 dataset/split 隔离**：写入 `output_root/{dataset}/{split}/.checkpoints/`
- **兼容旧位置**：读取时若新位置不存在，会 fallback 到旧的 `output_root/.checkpoints/`（只读）

### Files changed

- `metadata/src/openspatial_metadata/cli.py`
- `metadata/tests/test_framework_unittest.py`
- `metadata/tests/test_cli_checkpoints_scoped.py`

### Verification

- `pytest metadata/tests -q` → `44 passed`

