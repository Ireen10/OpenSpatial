## 方案设计（Design）：并行与大规模 metadata CLI

> 状态：草案，待对齐后再写 `plan.md` / `test_plan.md`。上一轮框架交付见 `metadata/plans/2026-04-14_0100_metadata_framework/`。

### 背景与目标

- **背景**：实际数据集体量大，多 JSONL 分片常见；当前 CLI 为**顺序**处理，`--num-workers` / `global.num_workers` 未接线。
- **目标（必须可验证）**：
  - 在**不破坏**现有「每 JSONL 输入 → 独立 `.out.jsonl` + 独立 checkpoint」模型的前提下，支持**按输入文件粒度**的并行（默认或配置可调）。
  - 明确 **`json_files` 聚合写 `part-*.jsonl`** 在并行下的策略（禁止并行 / 单写者队列 / 改分片策略三选一），并在文档与测试中写死。
- **非目标（本轮可先不做）**：
  - 单机多机分布式；GPU；跨数据集并行（仍按 dataset config 顺序即可，除非另有需求）。

### 术语与约束

- **文件级并行**：每个 worker 独占一组输入文件及其输出路径，**禁止**多进程同时写同一输出文件。
- **输入约束**：JSONL 多文件天然可并行；`json_files` 多文件共享聚合 writer，需单独设计。
- **兼容性**：保留 `resume` / checkpoint 语义；Windows `spawn` 下 CLI 入口需可安全 `multiprocessing`（若用进程池）。

### 核心流程（草案）

- 解析 `num_workers = max(0, min(cli_flag, global, len(files))))`（具体合并规则待对齐）。
- `input_type == jsonl"` 且 `len(files) > 1` 且 `num_workers > 1`：使用进程池或线程池，将 `_process_jsonl_file(ip, op, ...)` 作为任务单元提交。
- `json_files`：首轮实现可选 **强制 `num_workers` 降为 1** 并打日志/文档说明，或实现单进程多文件顺序（与现状一致）直至有单独设计。

### 风险与未决问题

- **风险**：子进程异常传播、部分成功部分失败时的 checkpoint 一致性；IO 饱和导致 `num_workers` 过大反而变慢。
- **未决问题**：
  - 进程 vs 线程（CPU 绑定适配器 vs 纯 IO 透传）默认选哪个？
  - `strict` / 错误汇总是否在并行轮次统一暴露？
