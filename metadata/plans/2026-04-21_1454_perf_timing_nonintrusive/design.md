## Design: 非侵入性能埋点（不影响进度条）

### 目标

- 为 metadata pipeline 增加更细粒度性能埋点（checkpoint / dump / 持久化写盘）。
- 不改变运行时进度条显示行为，不新增实时日志输出。

### 约束

- 仅通过 `PhaseTimer`/`timed_phase` 聚合数据。
- 输出仍只在 `--timing` 结束汇总打印时出现。
- 不修改 `_log` / `_tqdm` 调用路径与频率。

### 方案

- 在 `cli.py` 增加以下 phase：
  - `checkpoint_write`：`_write_checkpoint_atomic` 调用时间
  - `metadata_dump`：`_md_dump` 调用时间
  - `persist_noqa_write` / `persist_qa_write`：batch 写盘分支时间
- 补充测试保证埋点不会触发额外进度输出行为（通过不引入新 `_log` 调用、保留原测试通过验证）。
