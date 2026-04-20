# change_log — multi-adapter chain

## What changed

- **`DatasetConfig`**: optional `adapters: List[AdapterSpec]`; effective chain from `adapter_specs_for_dataset()` — non-empty `adapters` wins; else legacy `adapter`; empty `adapters` list falls back to `adapter`.
- **`resolve_adapter`**: validates import for every spec in the effective chain.
- **`ChainedAdapter`** (`adapters/chained.py`): ordered `convert` composition.
- **`cli._make_adapter_factory`**: builds one instance per spec (same ctor injection as before); single instance returned as-is; multiple wrapped in `ChainedAdapter`.
- **Docs**: `metadata/docs/config_yaml_zh.md` (`adapters` section + `adapter` description fix).

## Tests

- `metadata/tests/test_adapter_chain.py` (5 tests).
- Full suite: `python -m pytest metadata/tests -q` → **82 passed**.

## Deviations

- None.
