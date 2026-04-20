# Adapter chain strict metadata (design)

## Goal

Optional contract enforcement on `ChainedAdapter`:

1. **`strict_dict`**: each `convert` must return a `dict` (fail fast if not).
2. **`validate_metadata_from_adapter_index`**: before invoking the adapter at index `k` for every `k >= N`, validate the current payload as `MetadataV0`. Typical **`N=1`**: first adapter may consume raw source; from the second adapter onward inputs are metadata-shaped.

Default **`N=None`**: no in-chain validation (backward compatible with existing chains and unit tests that use arbitrary dicts).

## Config

`dataset.yaml`:

```yaml
adapter_chain:
  strict_dict: true
  validate_metadata_from_adapter_index: 1
```

`AdapterChainConfig` on `DatasetConfig`; only consulted when multiple adapters are in use (`ChainedAdapter`).
