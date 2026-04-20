# Test plan

| ID | Case |
|----|------|
| T1 | `strict_dict=True` + convert returns non-dict → TypeError |
| T2 | `validate_metadata_from_adapter_index=1` + first step outputs valid MetadataV0 dict → second step runs |
| T3 | Same + first step outputs invalid metadata → Validation error before second step |
| T4 | Default (no `adapter_chain` / None) → existing `ChainedAdapter` behavior unchanged |

Command: `pytest metadata/tests/test_adapter_chain.py metadata/tests -q`
