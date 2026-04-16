## 方案设计（Design）：并行与大规模 metadata CLI

> 状态：**Design 已定稿**（仅 `strict=True`；不实现 `strict=False`）。`plan.md` / `test_plan.md` 随本轮实现编写。上一轮框架见 `metadata/plans/2026-04-14_1737_metadata_framework/`。

### 背景与目标

- **背景**：实际数据集体量大，多 JSONL 分片常见；当前 CLI 为**顺序**处理，`--num-workers` / `global.num_workers` 未接线。
- **目标（必须可验证）**：
  - 在**不破坏**现有「每 JSONL 输入 → 独立 `.out.jsonl` + 独立 checkpoint」模型的前提下，支持**按输入文件粒度**的并行（默认或配置可调）。
  - **`json_files` 聚合写 `part-*.jsonl` 的并行策略（已选定）**：各 worker **只处理单个输入 JSON 文件**（读入、适配/透传），将**处理结果**回传给主进程；主进程维护一个 **batch 列表**，当累计条数达到 `batch_size`（或与 global 约定的一致阈值）时，**仅由主进程**写入 `part-*.jsonl` 并轮转 part 序号。**禁止** worker 直接打开或写入聚合输出文件，从而避免写冲突。该策略须在 `plan.md` / `test_plan.md` / `metadata/docs/config_yaml_zh.md` 中写死并与实现对齐。
- **非目标（本轮可先不做）**：
  - 单机多机分布式；GPU；跨数据集并行（仍按 dataset config 顺序即可，除非另有需求）。

### 术语与约束

- **文件级并行**：每个 worker 独占**单个输入文件**上的读与计算；**写盘**在 JSONL 场景为每输入对应一个 `.out.jsonl`；在 `json_files` 场景为**主进程单写者**写 `part-*.jsonl`。
- **输入约束**：JSONL 多文件可并行处理且各自输出独立；`json_files` 采用 **worker 回传 + 主进程 batch flush**，无多写者。
- **运行与可移植性**：**以 Linux 开发/运行为主**；路径与并发语义按 **POSIX** 习惯设计（`pathlib`、不依赖盘符/反斜杠约定、不在逻辑里绑定 Windows-only API）。若日后需在 Windows 上跑，再在 plan/CI 中单列验证项，**不作为本轮设计约束**。

### 核心流程（草案）

- 解析 `num_workers = max(0, min(cli_flag, global, len(files))))`（具体合并规则在 `plan.md` 对齐）。
- **`input_type == jsonl`** 且多文件且 `num_workers > 1`：进程池或线程池，以「单输入 JSONL 文件」为任务单元，调用与现状等价的处理逻辑（每任务写自己的 `.out.jsonl` + checkpoint）。
- **`input_type == json_files`** 且 `num_workers > 1`：
  1. 主进程提交任务时可按 `expand_inputs` 展开列表顺序（便于复现与调试）；**不要求**输出 `part-*.jsonl` 中行序与输入文件顺序一致，但每条记录须带 **`aux.record_ref`（至少含 `input_file`）**，以便从输出**反向追溯**到源 JSON 路径（`batch_size` 典型约 1000，与 global 对齐）。
  2. Worker：读一个 JSON 文件 → 产出一条（或固定条数）metadata 记录 → **仅通过 IPC 返回值**交给主进程；**不写** `part-*.jsonl`。
  3. 主进程：将返回记录依次 `append` 到 batch；`len(batch) >= batch_size` 时写入当前 `part-*.jsonl`、清空 batch、递增 part 索引；收尾 flush 剩余 batch。
  4. **Checkpoint（建议）**：按**输入文件**粒度更新，但**不要**在「worker 已返回、记录尚在主进程 batch 内存」时标完成；应在**包含该输入对应记录的那次 `part-*.jsonl` 写入且 flush 成功之后**再更新（一次 flush 可对应多条输入时，可对该 batch 内涉及的所有输入**批量**写 checkpoint）。收尾对不足 `batch_size` 的剩余 batch 同样 **先 flush 再更新**。这样 resume 与**已落盘**语义一致，避免进程崩溃导致「已 checkpoint、无输出」。字段与 `resume` 细节在 `plan.md` 定稿。

### 顺序、内存与错误（本策略下须显式约定）

- **`json_files` + 并行**：**不强制**输出行序与输入文件列表一致；以 **`aux.record_ref.input_file`（及现有 `input_index` 等）** 保证可追溯。测试用例应断言：任意输出行可解析并映射回合法源路径。
- **`jsonl`**：单文件内行序仍与输入一致（流式读写）；多文件并行时各 `.out.jsonl` 仍 1:1，文件间顺序不要求与 glob 展开序一致，除非下游有需求（若有则写入 plan）。
- **内存**：batch 列表峰值约为 `batch_size`（典型 ~1000）条记录；单条 metadata 很大时需下调 `batch_size` 或监控 RSS。
- **风险**：子进程/线程异常、部分 flush 成功后的 checkpoint 一致性；`num_workers` 过大导致 IO 饱和。
- **已定决策**：
  1. **进程 vs 线程（本轮）**：仅实现 **`ThreadPoolExecutor`**（`num_workers>1` 时）。典型负载：**小单文件 JSON（`json_files`）**、**约千行量级 JSONL 分片**；偏 I/O + 轻 CPU。`ProcessPoolExecutor` / `--parallel-backend process` **不纳入本轮**（另开变更再写 design）。
  2. **`strict`（本轮唯一语义）**：**仅支持 `strict=True`**（与 global 默认一致）；**不实现 `strict=False` / best-effort**，也不在 plan 中预留钩子，避免半套语义。
     - 任一 worker 处理某输入抛错 → **立即停止向池内 `submit` 新任务**。
     - **在途任务**：对**尚未开始**的 pending 任务尽量取消（`shutdown(..., cancel_futures=True)` 在 Python 3.9+ 可用时）；对**已在执行**的任务 **等待其结束**（`wait=True`），再统一退出，避免线程池与主进程状态撕裂。
     - 进程以 **非零退出码** 结束；向 **stderr** 打印 **失败输入路径 + 异常摘要**（可多行若合并多个失败，但 strict 下通常首个失败即停收）。
     - **Checkpoint**：仅对已 **flush** 到 `part-*.jsonl` / `.out.jsonl` 的输入更新；**仅 worker 返回、尚未进入已 flush batch 的输入不写 checkpoint**。失败退出前：若主进程内存中仍有**已聚合、尚未 flush**的 batch，**应先按正常路径 flush 并更新 checkpoint**（避免已成功 worker 的结果丢失），再 `sys.exit(1)`；细节见 `plan.md`。
