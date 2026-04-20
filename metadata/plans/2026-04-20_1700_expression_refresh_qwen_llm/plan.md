# Plan

1. Extend `AdapterSpec` with `params`; merge into adapter ctor in `_instantiate_one_adapter`; pass `dataset_config_path` from `_make_adapter_factory`.
2. Add `llm/openai_compatible.py` and `adapters/expression_refresh_qwen.py`.
3. Tests: stub client, single / multi / null phrase / `resolve_adapter` import.
