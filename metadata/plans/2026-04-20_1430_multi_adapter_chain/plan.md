# Multi-adapter chain (execution plan)

## Code

1. `metadata/src/openspatial_metadata/config/schema.py` — add `adapters: Optional[List[AdapterSpec]]`.
2. `metadata/src/openspatial_metadata/config/loader.py` — `resolve_adapter`: iterate effective adapter specs (precedence: non-empty `adapters` > `adapter`).
3. `metadata/src/openspatial_metadata/adapters/chained.py` — `ChainedAdapter`.
4. `metadata/src/openspatial_metadata/cli.py` — refactor adapter construction into `_instantiate_adapter_from_spec`; `_make_adapter_factory` uses `dataset_adapter_specs(ds)` and returns single instance or `ChainedAdapter`.

## Docs

- `metadata/docs/config_yaml_zh.md` — document `adapters` list and precedence vs `adapter`.

## Artifacts

- `design.md`, `plan.md`, `test_plan.md`, `change_log.md` (this directory).
