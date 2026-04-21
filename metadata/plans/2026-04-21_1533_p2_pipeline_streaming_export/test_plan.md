## 测试计划

本计划覆盖 P2-A / P2-B 的核心风险：导出流式改造正确性、默认开启流水路径的稳定性、关闭开关后的回退等价性。

---

## T1 - 流式分包正确性（P2-A）

- 目标功能点：`rows_per_part` 固定行数分包改为流式写入
- 用例：
  1. 输入总行数恰好为 `N * rows_per_part`；
  2. 输入总行数为 `N * rows_per_part + remainder`。
- 断言：
  - bundle 数量与每个 bundle 行数符合预期；
  - `images/*.tar` 与 `jsonl/*.jsonl` 一一对应；
  - 不依赖“先攒满大 buffer”也能得到一致结果。

## T2 - row_align 尾部策略（P2-A）

- 目标功能点：`training_remainder_mode=drop` 默认行为兼容
- 用例：
  1. `drop` 模式下 remainder 被丢弃并打印明确告警；
  2. （可选）`sidecar` 模式下 remainder 被写入 sidecar 文件。
- 断言：
  - `drop` 模式结果与历史行为一致；
  - `sidecar` 模式不影响主 bundle 完整性。

---

## T3 - 默认开启流水路径（P2-B）

- 目标功能点：`pipeline_streaming_enabled=true` 默认启用
- 用例：
  1. 不显式配置该参数，直接跑训练 pipeline；
  2. 输入包含可生成与不可生成 QA 的混合样本。
- 断言：
  - 默认命中新流水路径；
  - 输出 schema、QA 产出规则、checkpoint 语义不回退；
  - tqdm/日志行为不出现明显扰动。

## T4 - 关闭开关回退等价（P2-B）

- 目标功能点：`pipeline_streaming_enabled=false` 可回退
- 用例：
  1. 同一输入分别在 `true/false` 下运行；
  2. 对关键输出做结构与计数对比（允许顺序策略内差异）。
- 断言：
  - 功能等价（样本数、qa_items 数、bundle 数、关键字段一致）；
  - `false` 模式明确走旧路径，便于回滚。

---

## T5 - 有界队列与内存安全（P2-B）

- 目标功能点：有界 backpressure 防止无界增长
- 用例：
  1. 人为降低 `pipeline_queue_size`，模拟下游慢速；
  2. 长输入连续处理。
- 断言：
  - 队列不会无界增长；
  - 处理可持续推进，不出现死锁；
  - 峰值内存不随总样本量线性飙升（至少在压测窗口内可观测）。

---

## T6 - 回归套件（必须通过）

- `metadata/tests/test_training_pipeline_batching_perf.py`
- `metadata/tests/test_io_json_resume_skip.py`
- `metadata/tests/test_cli_phase_timing.py`
- `metadata/tests/test_qa_tasks_registry.py`
- `metadata/tests/test_qa_spatial_relation_2d.py`

断言：所有既有关键回归保持通过，确保 P2 不破坏先前修复。
