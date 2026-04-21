## Design: training pipeline batching perf 优化

### 背景

当前 `jsonl + pipelines(ensure_qa/export_training)` 路径下，`_process_jsonl_file_training_pipeline` 采用逐条持久化与逐条 checkpoint，导致：

- `batch_size` 在 training pipeline 分支不生效；
- 高并发下小 IO（checkpoint 原子写 + 单条 JSONL write）放大；
- `persist_noqa=false` 时仍存在不必要的 `noqa` dump。

### 目标

1. 让 training pipeline 分支也按 `batch_size` 批量持久化与 checkpoint。
2. 消除 `persist_noqa=false` 且无需写 QA 时的冗余 `noqa` dump。
3. 保持输出内容、顺序语义和现有功能行为不变。

### 方案

- 为 `_process_jsonl_file_training_pipeline` 增加 `batch_size` 参数。
- 在该函数内引入 pending buffer（`noqa` / `qa` 各自列表）：
  - 到达 `batch_size` 或收尾时统一 `write_records`；
  - checkpoint 与 batch flush 同步，减少原子写频率。
- 并行路径中，改为按“保序写出点”再决定是否 dump `md_noqa`，避免在 `persist_noqa=false` 时提前 dump。

### 风险与缓解

- 风险：checkpoint 频率降低后，异常中断时可能回退到最近一批。
  - 缓解：保持顺序与 checkpoint 语义一致（next_input_index 对齐已 flush 数据），并以测试覆盖边界。
