## 执行计划（Plan）：并行 metadata CLI（Linux / strict-only）

> 依据：`metadata/plans/2026-04-15_0200_parallel_metadata_cli/design.md`（已定稿）。本轮**仅** `strict=True`；**仅** `ThreadPoolExecutor`；**不**实现 `strict=False`、**不**实现 `ProcessPoolExecutor`。

### 交付物清单

- **文档**：更新 `metadata/docs/config_yaml_zh.md`（`num_workers` 行为、strict、checkpoint、并行语义）；必要时更新 `metadata/README.md` CLI 说明。
- **代码**：`metadata/src/openspatial_metadata/cli.py`（核心）及按需拆出的并行辅助模块（若单文件过长则 `cli_parallel.py` 或 `runtime/parallel.py`，保持 import 清晰）。
- **配置**：无 schema 破坏性变更；`global.yaml` / `--num-workers` 语义写进文档。
- **样例/fixtures**：在 `metadata/tests/` 增加可稳定触发并行与失败路径的夹具（小 JSON 集、双 JSONL 分片已部分存在，可复用并增补）。

### 文档同步（与本变更一并交付）

- [x] `metadata/docs/config_yaml_zh.md`
- [x] `metadata/docs/metadata_spec_v0_zh.md`：**无**（v0 JSON 形状本轮不变，除非实现中发现矛盾）
- [x] `metadata/README.md`（若 CLI 参数或推荐命令变化）
- [x] `metadata/plans/2026-04-15_0200_parallel_metadata_cli/test_plan.md`（**已起草**；实现完成后按用例逐项对齐并勾选）
- [x] `metadata/docs/project_progress_zh.md`（**整轮**收束：实现 + 自测通过 + `change_log.md` 之后；勿仅因文档齐备而更新）
- [x] 其他：**无**

### `num_workers` 生效规则（写死）

- 记 `cli_n = --num-workers` 解析值（默认 `0` 表示「**未覆盖**，沿用 global」）。
- 记 `g_n = global.num_workers`，`F = len(files)` 当前 split 展开后的输入文件数。
- **有效并行度**：`effective = cli_n if cli_n > 0 else g_n`；再 `effective = min(effective, F)`；若 `effective <= 1`，**整段 split 走现有顺序逻辑**（与当前行为一致，零回归）。
- **上限（可选）**：可在代码中设硬顶（如 `min(effective, 32)`）并在文档说明防 IO 饱和；若采用，写入 `test_plan` 一条断言。

### `strict=True` 错误与线程池收尾（写死）

- 仅支持 `global.strict is True`（当前 schema 默认）；CLI **不**新增 `strict=False` 开关。
- 并行路径中，任一 worker 对某输入抛出未捕获异常：
  1. **不再**向 `ThreadPoolExecutor` 提交新任务。
  2. 调用 `executor.shutdown(wait=True, cancel_futures=True)`（Python 3.9+）或等价：**取消尚未开始的 pending**；**等待已在运行**的任务结束。
  3. 向 **stderr** 打印：`input_path` + 异常类型与简短消息（可多行若聚合多个失败；通常首个失败即触发）。
  4. **`sys.exit(1)`**（或 `raise SystemExit(1)` 自 `main` 统一出口，便于测试 mock）。
- **内存中未 flush 的 batch**：失败退出前，**先将当前 batch 执行一次与正常路径相同的 flush**（写 `part-*.jsonl`、递增 part），并对本 batch 内记录**批量更新 checkpoint**，避免已成功 worker 的结果因崩溃/退出而丢失；若 flush 本身失败则退出码仍为失败，checkpoint 以「已成功原子写」为准（见实现注释）。
- **与 design 对齐**：checkpoint **永不**在「仅 worker 返回、尚未进入已 flush 的 batch」上标记完成；仍仅在 **flush 成功后** 更新对应输入的 checkpoint。

### 任务拆解

#### T1：JSONL 多文件并行（文件级）

- **目标**：`input_type=jsonl` 且 `effective>1` 时，以**单输入文件**为任务在线程池中跑现有 `_process_jsonl_file` 逻辑（每文件独立输出与 checkpoint，**不改**写模型）。
- **文件**：`cli.py`（或拆出辅助函数）。
- **完成条件**：双 JSONL 集成测试在 `num_workers=2` 下通过；`num_workers=0/1` 与旧行为一致。

#### T2：`json_files` 并行 + 主进程单写者

- **目标**：`input_type=json_files` 且 `effective>1` 时，worker 仅 `Path -> dict`（读 JSON + 透传构造 `aux.record_ref`）；主进程 `as_completed` 或等价收集结果 → `batch` → 满 `batch_size` flush；**flush 后**批量更新涉及输入的 checkpoint；不要求输出行序与输入列表一致，但 **`aux.record_ref.input_file` 可解析且路径存在**。
- **文件**：`cli.py` + 必要小函数（纯函数便于单测）。
- **完成条件**：多小 JSON + `num_workers>1` 的集成测试；随机完成顺序下仍可追溯每条记录到源文件。

#### T3：接线 `num_workers` 与 CLI

- **目标**：`main()` 读取 `args.num_workers` 与 `g.num_workers` 按上节规则合并；传入 T1/T2。
- **文件**：`cli.py`。
- **完成条件**：`--num-workers` 覆盖 global 的用例；`0` 表示用 global 的用例。

#### T4：strict 失败路径与退出码

- **目标**：构造 worker 抛错（坏 JSON 文件或测试注入），断言 stderr 含路径、进程退出码 `1`、已 flush 部分 checkpoint 仍存在且可 resume。
- **文件**：测试 + `cli.py`。
- **完成条件**：`test_plan.md` 中 IT 全部可运行通过。

#### T5：文档

- **目标**：`config_yaml_zh.md` 与 README 与 design/plan 一致；删除或改写「未实现并行」类表述。
- **完成条件**：自检清单勾选。

### 里程碑与回滚

- **里程碑 M1**：T1 完成 + 测试（JSONL 并行）。
- **里程碑 M2**：T2–T4 完成 + 测试（json_files 并行 + strict）。
- **里程碑 M3**：T5 文档。
- **回滚**：单提交可 revert；并行与顺序由 `effective<=1` 开关隔离，回滚后默认 `num_workers=0` 即走 global（常为 0）顺序路径。

### 风险与缓解

- **resume 与重复行**：若失败前已 flush 部分 part，resume 时须依赖 **checkpoint 跳过已完成输入**；未 flush 的输入会重跑——设计已接受；实现上保证 **checkpoint 与 flush 同一原子顺序**。
- **GIL**：默认定位于 I/O 型负载；CPU 重场景留待后续 `ProcessPool` 变更。
