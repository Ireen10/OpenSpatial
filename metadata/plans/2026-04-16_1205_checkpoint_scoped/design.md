## Design: per-dataset/split checkpoints

### Goal

将断点续传（checkpoint）从全局 `output_root/.checkpoints/` 改为按输出目录隔离：

- 新位置：`output_root/{dataset}/{split}/.checkpoints/`

使得：

- 删除某个 `output_root/{dataset}/{split}` 输出目录即可“只重跑该数据集/该 split”，不会被遗留 checkpoint 误判为已完成
- 批量跑多个数据集时，各自断点互不影响

### Non-goals

- 不改变 checkpoint 的语义（JSONL 仍是 `next_input_index`；json_files 仍是 `done=true`）
- 不引入新依赖/不做进度条增强

### Compatibility

考虑已有用户在旧位置存在 checkpoint：

- **读取**：优先读新位置；若新位置不存在且旧位置存在，则读取旧位置（兼容）
- **写入**：只写新位置（逐步迁移）

### Data model (unchanged)

Checkpoint 文件仍为 JSON：

- JSONL：`{"input_file": "...", "next_input_index": N, "errors_count": 0}`
- json_files：`{"input_file": "...", "done": true, "errors_count": 0}`

文件名 key 仍使用 `md5(input_file)`，但由于目录已隔离，不再需要在 key 里编码 dataset/split。

