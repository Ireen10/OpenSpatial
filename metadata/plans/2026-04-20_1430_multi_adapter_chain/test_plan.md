# Multi-adapter chain (test plan)

| ID | What | Maps to plan |
|----|------|----------------|
| T1 | Unit: `ChainedAdapter` applies two steps in order (second sees output of first). | `ChainedAdapter` |
| T2 | Config: `load_dataset_config` accepts YAML with `adapters:` list; `resolve_adapter` imports all. | loader + schema |
| T3 | Regression: `pytest metadata/tests` full suite passes (single-`adapter` datasets unchanged). | backward compatibility |

**Commands**

- `python -m pytest metadata/tests/test_adapter_chain.py -q`
- `python -m pytest metadata/tests -q`
