## Change log: 2026-04-20_2130_llm_refresh_multi_bbox

### Added

- `ExpressionRefreshQwenAdapter`
  - `refresh_mode`:
    - `per_object` (default): one LLM call per bbox (image includes a red box).
    - `all_objects`: one LLM call per record (image optionally draws all boxes and labels `#1..#N`).
  - `draw_boxes` (bool): when `refresh_mode=all_objects`, controls whether the image sent to the LLM has all boxes overlaid.
  - In `all_objects` mode, model output supports:
    - `objects[].index` (1-based)
    - `objects[].bbox_xyxy_norm_1000` (echo for post-validation)
    - `objects[].category`
    - `objects[].phrase` (unique, non-spatial; `null` allowed)
  - Post-validation: records `bbox_mismatch` errors in `aux.expression_refresh.errors` when echoed bbox differs from input.

- `ObjectDedupExactAdapter`
  - Added `key_mode`:
    - `bbox_phrase` (default, existing behavior)
    - `bbox` (bbox-only dedup), useful before LLM refresh to avoid forcing distinct phrases for identical regions.

### Updated

- Template `metadata/templates/configs_minimal/datasets/e2e_d_grounding_refresh_qa_training/dataset.yaml`
  - Documented `refresh_mode` / `draw_boxes`
  - Added an optional pre-refresh bbox-only dedup step example

### Tests

- Extended `metadata/tests/test_expression_refresh_qwen.py` to cover:
  - `all_objects` single-call behavior + query rewrite
  - bbox mismatch recording
- Extended `metadata/tests/test_object_dedup_exact_adapter.py` to cover `key_mode=bbox`.

