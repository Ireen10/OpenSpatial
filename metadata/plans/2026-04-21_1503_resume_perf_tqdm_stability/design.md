## Design: resume 续跑性能 + tqdm 稳定性修复

### 现象

1. `--resume` 场景下，读取 checkpoint 后仍长时间“卡住”。
2. `progress=tqdm` 时并行运行中控制台排版被高频刷新打乱。

### 根因（代码路径）

- 续跑时虽然有 `next_input_index`，但 `iter_jsonl` 仍会对已处理行执行 `json.loads`，只是在上层循环里 `continue` 丢弃，导致跳过阶段 CPU 浪费明显。
- 并行文件处理时在 `tqdm` 模式仍输出高频 done 日志（`_log` -> `tqdm.write`），与多进度条刷新互相干扰。

### 方案

1. `iter_jsonl` 增加 `start_index` 参数：
   - `idx < start_index` 时只读行不解析，不做 `json.loads`。
   - CLI 在 resume 时传入 `start_index=next_idx`，并移除重复的 `if ref.input_index < next_idx` 分支。
2. `tqdm` 模式下抑制并行 worker 的高频 done 日志：
   - 保留进度条刷新，不额外插入 `tqdm.write` 的 done 行。

### 兼容性

- 业务语义不变：输入输出、checkpoint 语义、处理顺序不变。
- 仅优化跳过阶段与终端显示稳定性。
