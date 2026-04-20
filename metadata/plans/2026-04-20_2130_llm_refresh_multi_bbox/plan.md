## Execution plan: LLM refresh multi-bbox mode

### Scope

- Extend `ExpressionRefreshQwenAdapter` to support **single-call per record** refresh (`refresh_mode=all_objects`).
- Add adapter params:
  - `refresh_mode`: `per_object` (default) | `all_objects`
  - `draw_boxes`: bool (default `true` for `all_objects`)
- In `all_objects` mode, require the model to return per-object:
  - `index` (1-based)
  - `bbox_xyxy_norm_1000` (echo)
  - `category`
  - `phrase` (unique, non-spatial; `null` allowed)
- Add post-validation:
  - `bbox_xyxy_norm_1000` echoed must exactly match input bbox for that index; mismatch is recorded in `aux.expression_refresh.errors`.
- Add bbox-only dedup option to `ObjectDedupExactAdapter` so it can run **before** LLM refresh.

### Implementation steps

1) **Adapter: prompt + rendering helpers**
   - Add `_image_jpeg_data_url(base_rgb)` for “no overlay” case.
   - Add `_image_jpeg_data_url_with_boxes(base_rgb, boxes, coord_scale)`:
     - draws all boxes with distinct colors and labels `#1..#N`
   - Add `_user_text_all_objects(...)` that:
     - lists all bboxes with index
     - states all boxes are different instances
     - forbids spatial/ordinal wording and forbids using index in phrase
     - defines JSON output schema

2) **Adapter: `refresh_mode=all_objects`**
   - Build a stable ordered task list of objects:
     - first: de-duplicated candidates in query order (first occurrence)
     - then: remaining objects not referenced by any query
   - Build one vision message (image + text).
   - Call LLM once, parse JSON.
   - Apply updates by index (authoritative), record bbox mismatch errors.
   - Drop objects where phrase is `null` (existing behavior), then rewrite queries (existing behavior).

3) **Adapter: keep `per_object` mode**
   - Preserve existing per-object call path and its optional intra-record parallelism knobs.

4) **Dedup adapter: bbox-only key mode**
   - Extend `ObjectDedupExactAdapter` with `key_mode`:
     - `bbox_phrase` (default, existing)
     - `bbox` (new)
   - Ensure query remapping behaves the same as existing dedup.

5) **Templates/docs**
   - Update `e2e_d_grounding_refresh_qa_training/dataset.yaml` to document:
     - `refresh_mode: all_objects`
     - `draw_boxes: true/false`
   - (Optional) add a commented chain example showing bbox-only dedup placed before refresh.

6) **Verification**
   - Add unit tests for:
     - `all_objects` JSON parsing + index mapping + query rewrite
     - bbox mismatch recorded
     - bbox-only dedup key mode
   - Run `python -m pytest metadata/tests -q`.

