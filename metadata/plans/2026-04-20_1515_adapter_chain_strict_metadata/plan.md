# Plan

1. `config/schema.py`: `AdapterChainConfig` + `DatasetConfig.adapter_chain`.
2. `adapters/chained.py`: constructor args; validation helper using `MetadataV0` parse/model_validate.
3. `cli.py`: pass `adapter_chain` from dataset into `ChainedAdapter` when `len(instances) > 1`.
4. `docs/config_yaml_zh.md`: document `adapter_chain`.
5. Tests: `test_adapter_chain.py` additions; full `pytest metadata/tests`.
