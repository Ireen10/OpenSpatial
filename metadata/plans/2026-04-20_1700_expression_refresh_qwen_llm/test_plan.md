# Test plan

| Test | Expect |
|------|--------|
| `test_single_object_updates_phrase_and_category` | one LLM response updates object + query text |
| `test_null_phrase_drops_object_and_query` | empty objects/queries |
| `test_multi_two_candidates_two_calls` | two calls; `query_text` joined; no `gold_object_id` |
| `test_resolve_adapter_imports_expression_refresh` | YAML with `params` resolves |
