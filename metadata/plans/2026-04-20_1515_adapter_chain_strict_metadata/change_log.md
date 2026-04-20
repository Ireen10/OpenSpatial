# change_log — adapter_chain strict metadata

## What changed

- **`AdapterChainConfig`** (`strict_dict`, `validate_metadata_from_adapter_index`) on `DatasetConfig`.
- **`ChainedAdapter`**: optional strict dict return; optional MetadataV0 validation before adapters at index `>= N`.
- **`cli._make_adapter_factory`**: passes `adapter_chain` into `ChainedAdapter` when multiple instances.
- **Docs**: `metadata/docs/config_yaml_zh.md` (`adapter_chain` table).

## Tests

- `metadata/tests/test_adapter_chain.py` extended (strict dict, validate from index, yaml fields).
- `python -m pytest metadata/tests -q` → **86 passed**.

## Deviations

- None.
