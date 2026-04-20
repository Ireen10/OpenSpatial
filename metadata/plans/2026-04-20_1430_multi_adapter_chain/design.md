# Multi-adapter chain (design)

## Goal

Allow a dataset to declare **one or more** adapters applied **in order** to each input record (`convert` chaining), while **keeping existing single `adapter:` YAML** behavior unchanged.

## Behavior

- **New** optional field: `adapters:` — a **list** of the same `AdapterSpec` shape as today (`file_name` / `module`, `class_name`, etc.).
- **Precedence**: If `adapters` is present and **non-empty**, use it as the chain. Otherwise, if legacy **`adapter:`** is set, treat it as a **one-element** chain. If neither, no adapter (unchanged).
- **Semantics**: For chain `[A, B, C]`, each record becomes `C.convert(B.convert(A.convert(record)))` (left-to-right in YAML order).
- **Construction**: Same constructor injection rules as today (`dataset_name`, `split`, `coord_space`, `coord_scale`, `query_type_default`) for **each** instantiated class.

## Implementation sketch

- `DatasetConfig`: add `adapters: Optional[List[AdapterSpec]] = None`.
- `resolve_adapter`: validate import for **every** spec in the effective list.
- `ChainedAdapter` helper class with `convert` that folds over instances.
- `_make_adapter_factory`: build one instance per spec; if exactly one, return that instance (same object identity class as today); if multiple, wrap in `ChainedAdapter`.

## Non-goals

- No change to enrich / QA / training order.
- No async or parallel adapter execution within a record.
