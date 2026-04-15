# Change log：并行 metadata CLI（2026-04-15）

## 摘要

- **`cli.py`**：`effective_parallel_workers`（含 `F` 与硬顶 32）、JSONL 多文件 `ThreadPoolExecutor`、`json_files` 并行（worker 只读、主进程 flush + **flush 后** checkpoint）、`--num-workers` 与 `g.num_workers` 合并；`strict` 失败路径 stderr + `sys.exit(1)` + `shutdown(..., cancel_futures=True)`；`json_files` 失败前若 buffer 非空则先 flush。
- **测试**：`metadata/tests/test_parallel_cli.py`（UT-P1、IT-P1–IT-P4）；IT-P4 采用「好 JSONL + 坏 JSONL」并行失败后仅保留好分片并 `--resume`，断言最终 10 行且无重复 `sample_id`（不依赖竞态下坏分片是否晚于好分片完成）。`json_files` 用例使用显式路径列表以避免 Windows 上绝对路径 glob 差异。
- **文档**：`metadata/docs/config_yaml_zh.md`、`metadata/README.md`；`test_framework_unittest.py` 多 JSONL 用例 docstring 更新。

## 自测

- `python -m pytest metadata/tests -q`
- `python -m unittest discover -s metadata/tests -p "test_*.py" -q`

（开发机：Windows；质量门槛仍以 Linux 为准。）

## Linux 回归（留档）

- 独立 Linux 环境 clone 后：`pip install -e ./metadata`（及可选 `[dev]`）、仓库根执行 `python -m pytest metadata/tests -q` — **已通过**（与 `test_plan.md` 质量门槛一致）。

## 已知限制

- 未实现 `ProcessPoolExecutor`、`strict=False`。
- IT-P5（`effective<=1` 与顺序等价）主要由既有 `test_cli_io` / 多 JSONL 用例（默认 `num_workers: 0`）与 `test_parallel_cli` 中顺序 vs 并行对比覆盖。
