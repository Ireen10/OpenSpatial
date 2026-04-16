## Execution plan

### Code changes

- 更新 `openspatial_metadata/cli.py`：
  - 引入 “checkpoint_root” 概念，等于 `out_dir / ".checkpoints"`
  - `_checkpoint_path()` 改为接收 `checkpoint_root`
  - `_read_checkpoint()` 改为支持 fallback：新位置不存在时尝试旧位置 `output_root/.checkpoints`
  - 所有写 checkpoint 的地方改写入 `checkpoint_root`
  - 所有读取 checkpoint 的地方传入 `checkpoint_root`，并保留旧位置兼容读取

### Tests

- 新增/更新单测覆盖：
  - 运行一次 CLI 后，断言 checkpoint 文件出现在 `out_root/{dataset}/{split}/.checkpoints/`
  - 构造旧位置 checkpoint（`out_root/.checkpoints/...`），删除新位置 checkpoint，开启 resume 再跑，断言不会重复处理（兼容读取旧位置）

### Docs

- 本次无需改 wiki/spec（这是 CLI 行为变化，不是 metadata schema 变化）
- 仅在本计划目录记录 `change_log.md`

