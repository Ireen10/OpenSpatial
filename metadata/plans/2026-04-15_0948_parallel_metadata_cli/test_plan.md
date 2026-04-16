## 测试方案（Test Plan）：并行 metadata CLI

> 依据：`plan.md` §任务拆解 T1–T5、`design.md`。每项测试须能在 `plan.md` 中找到对应交付点。实现完成后须跑通本文件「质量门槛」中的命令并更新 `change_log.md`；**`project_progress_zh.md` 仅在整轮**（含自测与 change_log）**结束时**更新，见 `metadata/docs/project_progress_zh.md` 页首约定。

### 测试范围

- **覆盖范围**：
  - `num_workers` 合并规则：`--num-workers` 与 `global.num_workers`、`F` 的关系；`effective <= 1` 时与顺序路径行为一致（Plan §`num_workers` 生效规则、T3）。
  - JSONL：`effective > 1` 时多文件并行处理，输出 1:1、checkpoint 行为与顺序模式等价（Plan T1）。
  - `json_files`：`effective > 1` 时 worker 只回传、主进程 batch flush、`flush` 后 checkpoint、**不要求**行序与输入列表一致但 **`aux.record_ref.input_file` 可追溯**（Plan T2、Design §顺序）。
  - **strict**：worker 失败 → 停止提交、线程池 `shutdown(wait=True, cancel_futures=True)`（或等价）、stderr 含路径、**退出码 1**；失败前已 flush 的 checkpoint 保留；失败前内存 batch 按 Plan **先 flush 再退出**（Plan §`strict=True`、T4）。
  - （若实现硬顶）`effective` 不超过文档声明的上限（Plan §上限可选）。
- **不覆盖范围**：
  - `ProcessPoolExecutor`、跨机分布式、`strict=False`（本轮不实现）。
  - 性能压测、IO 饱和调参（仅保留可选说明，不做门槛）。

### 与 `plan.md` 的映射

| 测试编号 | 对应 Plan |
|----------|-----------|
| UT-P1 | T3：`num_workers` 合并（可在测试中通过调用内部纯函数或等价 CLI 场景） |
| IT-P1 | T1：JSONL 多文件 + `num_workers>1` |
| IT-P2 | T2：`json_files` 并行 + 追溯 + checkpoint-after-flush |
| IT-P3 | T4：strict 失败路径 |
| IT-P4 | T2+T4+resume：部分成功后失败再 `--resume` |
| IT-P5 | 回归：`effective<=1` 与现有顺序行为一致 |

---

### 测试执行方式

从仓库根目录：

```bash
python -m pytest metadata/tests -q
```

```bash
python -m unittest discover -s metadata/tests -p "test_*.py"
```

（实现时可将并行用例集中在 `metadata/tests/test_parallel_cli.py` 或扩展现有 `test_framework_unittest.py`，以最终实现为准。）

---

### 单元测试

#### UT-P1 `effective` 并行度合并（Plan T3、Plan §`num_workers`）✅

- **步骤**：对合并逻辑做表驱动测试（或在隔离的 `global` + CLI 参数组合下调用仅负责计算 `effective` 的函数）。
- **用例矩阵（示例）**：
  - `cli_n=0, g_n=0, F=5` → `effective=0` 或实现定义为「不并行」的最终值（与代码一致），断言**走顺序分支**。
  - `cli_n=0, g_n=3, F=5` → `effective=3`。
  - `cli_n=4, g_n=1, F=5` → `effective=4`。
  - `cli_n=10, g_n=3, F=5` → `effective=5`（`min` 夹断）。
  - `cli_n=2, g_n=8, F=3` → `effective=2`（`min` 夹断为文件数）。
- **断言**：与 `plan.md` 写死的公式逐条一致。

---

### 集成测试（CLI）

以下均在**临时目录**写 `dataset.yaml` / `global.yaml`（或复用 `metadata/tests/fixtures`），`--output-root` 指向临时目录；**绝对路径**写入 `inputs`，避免 cwd 歧义。

#### IT-P1 JSONL 多文件并行（Plan T1）✅

- **前置**：split `input_type=jsonl`，`inputs` 含至少两个绝对路径 JSONL（可复用 `jsonl_shard_alpha.jsonl` / `jsonl_shard_beta.jsonl`）。
- **配置**：`global.yaml` 中 `num_workers: 2`（或 CLI `--num-workers 2` 且 `cli_n=0` 时 `g_n=2`）。
- **步骤**：运行 `openspatial-metadata`（或 `python -m openspatial_metadata.cli`）。
- **断言**：
  - 两个 `.out.jsonl` 均存在且行数与输入一致；
  - `output_root/.checkpoints/` 下对每个输入各有 checkpoint；
  - 与 **IT-P5** 下同一配置但 `effective=1`（顺序）输出内容**等价**（逐行 JSON 解析后集合或顺序按实现约定比对：至少行数与 `sample_id` 集合一致）。

#### IT-P2 `json_files` 并行 + 追溯 + flush 后 checkpoint（Plan T2、Design）✅

- **前置**：≥4 个小 JSON 文件（可 fixture 子目录拷贝到临时目录）；`batch_size=2` 或 `3` 以强制多轮 `part-*`；`num_workers: 2`。
- **步骤**：运行 CLI 一次。
- **断言**：
  - 生成至少一个 `part-*.jsonl`；总行数等于输入文件数；
  - 对**每一输出行**：`json.loads` 后 `aux.record_ref.input_file` 存在且 `Path(...).is_file()` 为真（路径可追溯）；
  - 每个成功 flush 涉及的输入，在 **flush 之后** 存在 `done`/等价 checkpoint（与实现字段一致）；**无**「仅 worker 返回尚未 flush」即标 `done` 的情况（可通过在测试中 mock worker 延迟 + 检查 checkpoint 写入时机验证，若过难则退化为：最终全部输入均有 checkpoint 且与输出条数一致）。

#### IT-P3 strict：worker 失败（Plan T4、Design §strict）✅

- **前置**：在同一 split 的 JSON 列表中混入**一个非法 JSON** 文件（语法错）或 fixture 中专用坏文件；其余为合法小 JSON；`num_workers>=2`，`batch_size` 使至少有一批会先成功。
- **步骤**：运行 CLI，捕获 **stderr** 与 **退出码**（`pytest` 可用 `subprocess` 或封装 `main` 并 `pytest.raises(SystemExit(1))` 若 `main` 调 `sys.exit`）。
- **断言**：
  - 退出码为 **1**；
  - stderr 含**失败文件的绝对路径**（或 canonical 路径）及异常类型/信息片段；
  - 已实现「失败前 flush 内存 batch」时：磁盘上已存在的 `part-*.jsonl` 行数与**已成功 flush 的合法输入**一致；坏文件对应输入 **无** `done` checkpoint（或等价未完成标记）。

#### IT-P4 `json_files`：部分成功后失败再 `--resume`（Plan §风险与缓解、T2/T4）✅（JSONL 变体）

- **前置**：在 IT-P3 类似场景下，确保已有**部分**合法文件已 flush 且 checkpoint 已写；整体仍失败退出。（实现侧以 **JSONL 双分片** 构造：好分片可完整或部分完成，坏分片解析失败；第二次运行仅保留好分片并 `--resume`。）
- **步骤**：修复或移除坏文件（或换用仅合法文件的新 config）后，同一 `output_root` 带 `--resume` 再跑。
- **断言**：
  - 已 checkpoint 的输入**不会重复产生重复行**（或实现若选择「重写 part」须在 `change_log` 说明；默认期望 **skip + 续写** 无重复 `sample_id`/`input_file` 组合）；
  - 最终输出行数等于合法输入总数。

#### IT-P5 回归：`effective <= 1` 与顺序等价（Plan T3、§回滚）✅

- **配置 A**：`num_workers: 0` 且 CLI 不传 `--num-workers`，`g_n` 任意；或 `g_n=0`。
- **配置 B**：`--num-workers 1`。
- **断言**：与当前已实现之顺序行为（参考 `2026-04-14` IT-2 / 现有 `test_cli_io`）在相同 fixture 上输出一致或可比对等价。

---

### 质量门槛（Gate）

- **通过条件**：上述 UT-P1、IT-P1–IT-P4 在 CI / 本地 **Linux**（或开发机 POSIX 环境）上全部通过；`python -m pytest metadata/tests -q` 无失败。  
  **IT-P5**：由既有 `test_framework_unittest`（默认 `num_workers: 0` / 顺序）与 `test_parallel_cli.TestJsonlParallel`（同一 fixture 下 `num_workers: 0` vs `2` 输出集合一致）覆盖。
- **失败时如何定位**：
  - 看临时 `output_root` 下 `.checkpoints` 与 `part-*.jsonl`；
  - 对照 stderr 与 `plan.md` §strict / §checkpoint 条款是否实现偏差。

---

### 文档验收（与 Plan T5 对齐）

实现合并前勾选 `plan.md` 文档同步列表；并确认 `metadata/docs/config_yaml_zh.md` 中 **并行、`num_workers`、strict、checkpoint-after-flush** 与本文一致。
