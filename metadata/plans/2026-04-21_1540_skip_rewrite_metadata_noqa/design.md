## Goal

当 pipeline 的起点已经是 **metadata(noQA)**（即 `pipelines.to_metadata: false`，输入为 `MetadataV0` 且通常来自上游 `metadata_noqa/*.jsonl`）时：

- **不再**把每条输入记录“再写回”到本次 run 的 `{output_root}/{dataset}/{split}/metadata_noqa/`。
- 只输出真正新增的阶段产物：`metadata_qa/`（当 `ensure_qa: true`）以及 training bundles（当 `export_training: true` 且 `qa_items` 非空）。

这与最初 E2E-B / E2E-C 的语义一致：起点是 metadata，就不应再产生一份重复的 metadata_noqa 视图。


## Current behavior (problem)

当前 `openspatial_metadata.cli` 的 training pipeline 实现会 **始终写出** `metadata_noqa`（一行/输入记录），即使 `to_metadata=false` 时只是 `out = dict(record)` + `_md_validate`。

这会导致：

- 语义重复：输入已经是 metadata_noqa，还会被“重放”一遍到输出树的 metadata_noqa。
- 容易引入行数膨胀误解：尤其在 `resume=true` 或输出目录复用时，用户会观察到 `metadata_noqa` 行数远大于原始输入。


## Design decision

新增一个 **pipeline 级别**开关，让行为可控且默认不破坏已有依赖：

- 新增 `pipelines.persist_noqa: bool`（默认 `true`，保持现状）
- 对于“从 metadata_noqa 起步”的推荐模板（E2E-B / E2E-C），在模板里显式设置 `persist_noqa: false`

当 `persist_noqa=false` 时：

- training pipeline **不创建/不写入** `{split}/metadata_noqa/data_*.jsonl`
- checkpoint 仍按输入文件 + 行号推进（不依赖 metadata_noqa 落盘）
- `metadata_qa` 写入逻辑保持不变（有 `qa_items` 才写一行）
- training export 仍以 `metadata_qa` shards 为输入（现有逻辑）


## Compatibility / risks

- **默认兼容**：不改默认行为（`persist_noqa` 默认 true）。
- 依赖 `metadata_noqa/` 的下游（如某些 viz 期望）不会被默认破坏；当用户显式关闭后，相关 UI/脚本需要按“metadata_qa/ 视图”来浏览（或直接浏览输入文件）。
- 需要更新/新增测试，覆盖 `persist_noqa=false` 时不会写出 `metadata_noqa`，但仍会写出 `metadata_qa` 与 training。


## Non-goals

- 不引入 symlink/copy 机制去“复用输入 metadata_noqa 作为输出 metadata_noqa”（跨平台复杂，且与“只输出新增产物”的目标相悖）。
- 不改变 `ensure_qa` 的语义（`qa_items` 为空则不写 `metadata_qa`，不导出 training）。

