## 设计：dataset config 的 `meta` 贯通到输出 Metadata

### 背景

`dataset.yaml` 支持 `meta: { ... }`，但当前 CLI 流水线（read → adapter.convert → enrich → write）未使用这些信息。

同时 `MetadataV0.dataset` 具备 `source` 等字段（且允许 extra），适合承载数据集来源与附加元信息。

### 目标

- 在 CLI 输出的每条 record 中，将 dataset config 的 `meta` 写入 `MetadataV0.dataset`：
  - `ds.meta.source` → `out["dataset"]["source"]`
  - 其余 `ds.meta` 作为扩展字段保留（例如 `out["dataset"]["meta"] = ds.meta`）
- 不破坏 adapter 自己写入的 dataset 字段；优先级规则：
  - `name`/`version`/`split`：仍以 adapter/现有逻辑为主（仅在缺失时补齐）
  - `source`：若输出未提供，则使用 `ds.meta.source` 补齐；若输出已提供则不覆盖

### 执行位置

在 CLI 中对每条 `out`：

1. `out = adapter.convert(record)`（或 passthrough）
2. 注入 `aux.record_ref`
3. **应用 dataset meta 合并**
4. 若启用 enrich，执行 enrich
5. 写出 JSONL

### 兼容性

- 不要求 adapter 必须输出 `MetadataV0` 形状；但若启用 enrich 则本来就要求可 parse
- `DatasetV0` 允许 extra 字段，因此 `dataset.meta` 的扩展字段不会破坏 schema

### 测试

- 单测：构造一个最小 dict，调用 CLI 的合并函数，断言：
  - `dataset.source` 被补齐
  - `dataset.meta` 被写入
- E2E：refcoco 小样例输出应包含 `dataset.source == local_fixture`

