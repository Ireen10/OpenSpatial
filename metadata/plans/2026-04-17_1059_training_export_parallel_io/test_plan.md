# 测试计划（Test Plan）：训练导出多 part、并行与断点续跑

本测试计划逐条对应 `plan.md` 的任务拆解；实现完成后逐项勾选。

## 任务 1：record 流 runner（source/sink）

| ID | 对应 plan | 测试内容 | 预期 |
|---|---|---|---|
| T1a | 任务 1 | jsonl source：读取 1 个输入 shard（最小 1 行），能写出 `images/part_000000.tar`、`images/part_000000_tarinfo.json`、`jsonl/part_000000.jsonl` | 文件存在且结构可解析 |
| T1b | 任务 1 | json_files source：输入 2 个 json 文件（每文件 1 record），在 `batch_size=1` 时 flush 出 `part_000000.*` 与 `part_000001.*` | part id 单调递增、数量正确 |

## 任务 2：三步组合管线（E2E-A/B/C）

| ID | 链路 | 测试内容 | 预期 |
|---|---|---|---|
| T2a | E2E-C | metadata(withQA).jsonl → training bundle | 跑通，产物结构与 `training_data_format_zh.md` 一致 |
| T2b | E2E-B | metadata(noQA).jsonl → (annotation) → metadata(qa) + training | 同时产出 `metadata_noqa/` 与 `metadata_qa/` + training |
| T2c | E2E-A | grounding.jsonl → metadata(noQA) → metadata(qa) → training | 同时产出两份 metadata + training；单条 record 不中断（通过日志/计数断言） |

## 任务 3：I/O 对齐（part 映射 + 目录结构）

| ID | 对应 plan | 测试内容 | 预期 |
|---|---|---|---|
| T3a | 任务 3.1 | jsonl 1:1：输入 `a.jsonl` 写 `a.metadata.jsonl`（无 QA/带 QA 各一份），训练为 `part_000000.*`；输入 `b.jsonl` 对应 `part_000001.*` | 映射稳定可复现 |
| T3b | 任务 3.2 | json_files 聚合：`batch_size=2` 时 3 个 json 输入 → 2 个 part 输出 | flush 次数与 part 数一致 |

## 任务 4：断点续跑（resume）

### 4.1 jsonl source：next_input_index

| ID | 对应 plan | 测试内容 | 预期 |
|---|---|---|---|
| T4a | 任务 4.1 | 人为中断（例如处理到第 1 行就退出），checkpoint 写入 `next_input_index=1` | ckpt 存在且值正确 |
| T4b | 任务 4.1 | `--resume` 续跑：最终 `jsonl/part_*.jsonl` 行数与“一次跑完”一致 | 不重复、不丢失 |
| T4c | 任务 4.1 | resume 后 `tarinfo` 键集合与 jsonl 引用一致 | tarinfo 命中率 100% |

### 4.2 json_files source：done + next_part_id

| ID | 对应 plan | 测试内容 | 预期 |
|---|---|---|---|
| T4d | 任务 4.2 | 中断后 resume：已 done 的源文件不会再处理 | done 文件数不变 |
| T4e | 任务 4.2 | part id 不回退：续跑继续写 `part_{next}.tar` | part id 单调递增 |

## 任务 5：tar member 冲突去重

| ID | 对应 plan | 测试内容 | 预期 |
|---|---|---|---|
| T5a | 任务 5 | 构造同 part 内两条 record，`sample.image.path` 完全相同 | tarinfo key 唯一；第二条使用 `__r{input_index}` 后缀 |
| T5b | 任务 5 | 同一冲突场景下包含带框图 | 带框图使用 `_m{8hex}__r{input_index}.jpg` |

## 并行策略（回归）

| ID | 内容 | 预期 |
|---|---|---|
| P1 | jsonl source 文件粒度并行：2 个输入 shard、`num_workers=2` | 两个 part 都产出；不存在写入竞争导致的损坏 |

## 执行命令（建议）

实现阶段将新增/调整测试文件后，推荐以小范围开始：

```text
python -m pytest metadata/tests/test_export_*.py -q
python -m pytest metadata/tests/test_grounding_export_*.py -q
```

（最终以仓库内实际测试文件名为准。）

