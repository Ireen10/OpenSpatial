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

把“是否需要从 raw 生成 metadata（`to_metadata`）”与“是否要把 no-QA 视图落盘到 `metadata_noqa/`”解耦，并让默认行为更符合直觉：

- 新增 `pipelines.persist_noqa: Optional[bool]`：
  - **未设置（null）时的默认规则**：
    - 若 `to_metadata: true`（输入不是 metadata，确实在本次 run 生成了 metadata），则 **写出** `metadata_noqa/`
    - 若 `to_metadata: false`（输入已经是 metadata），则 **不写出** `metadata_noqa/`，只产出新增阶段（`metadata_qa/`、training）
  - 若显式设置：
    - `persist_noqa: true`：无论 `to_metadata` 如何，均写出 `metadata_noqa/`（兼容旧脚本/需要规范化落盘的用户）
    - `persist_noqa: false`：无论 `to_metadata` 如何，均不写出 `metadata_noqa/`

当最终决策为“不写 `metadata_noqa`”（即 `persist_noqa` 解析为 false）时：

- training pipeline **不创建/不写入** `{split}/metadata_noqa/data_*.jsonl`
- checkpoint 仍按输入文件 + 行号推进（不依赖 metadata_noqa 落盘）
- `metadata_qa` 写入逻辑保持不变（有 `qa_items` 才写一行）
- training export 仍以 `metadata_qa` shards 为输入（现有逻辑）


## Compatibility / risks

- **默认行为变化（按语义更合理）**：当 `to_metadata=false` 且未设置 `persist_noqa` 时，将不再写出 `metadata_noqa/`。
- 依赖 `metadata_noqa/` 的下游（如某些 viz 期望）可通过 `persist_noqa: true` 恢复旧行为。
- 需要更新/新增测试，覆盖 `persist_noqa=false` 时不会写出 `metadata_noqa`，但仍会写出 `metadata_qa` 与 training。


## Non-goals

- 不引入 symlink/copy 机制去“复用输入 metadata_noqa 作为输出 metadata_noqa”（跨平台复杂，且与“只输出新增产物”的目标相悖）。
- 不改变 `ensure_qa` 的语义（`qa_items` 为空则不写 `metadata_qa`，不导出 training）。

