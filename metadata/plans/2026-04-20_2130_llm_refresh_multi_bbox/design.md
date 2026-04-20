## Design: LLM refresh multi-bbox mode + category-aware QA refs

### Goal

Improve LLM-based referring-expression refresh quality and throughput for crowded/overlapping boxes by:

- Sending **all objects in a record** to the vision LLM in **one request** (single image + all bboxes).
- Explicitly stating that **each bbox is a distinct instance**, even if overlapping.
- Requiring the model to return a **JSON** payload that includes, per object:
  - `bbox_xyxy_norm_1000` (echoed back for post-check)
  - `category`
  - `phrase` (unique, non-spatial; `null` if impossible)
- Adding a dataset-level switch to **draw all boxes** on the image (or not), to evaluate visual clutter impact.
- Optionally **deduplicating identical bboxes before LLM refresh** (key = bbox only) to avoid “forced distinction” for duplicates.

### Non-goals

- Changing the metadata schema (we only change adapter behavior and prompts).
- Guaranteeing LLM uniqueness when the scene is genuinely ambiguous without spatial terms.

### Key changes

1) **ExpressionRefreshQwenAdapter: new refresh mode**

- Add `refresh_mode`:
  - `per_object` (current behavior; one LLM call per bbox)
  - `all_objects` (new; one LLM call per record, output list)

2) **Draw boxes toggle**

- Add `draw_boxes` (bool):
  - When `true`: draw **all** boxes on the image with visible outlines and **index labels** (e.g. `#1`, `#2`, …).
  - When `false`: send the original image (no overlay). Still provide bbox coordinates in the prompt.

3) **Returned bbox for post-check**

- LLM output must echo `bbox_xyxy_norm_1000` for each object.
- Adapter will **validate** returned bbox equals the input bbox (exact match on ints). If mismatch:
  - Count as `llm_error` for that object (policy controlled by existing `on_llm_error`), or
  - Ignore returned bbox and match by index (if we decide index is authoritative).

Decision: **index is authoritative** (stable ordering), bbox is used for **post-validation** only.

4) **Uniqueness constraints**

- Prompt explicitly requires: each `phrase` is **unique among the provided boxes**.
- Prompt explicitly forbids spatial terms (existing rule), and forbids using the **box index** in `phrase`.

5) **Dedup before refresh (bbox-only)**

- Extend the existing bbox+phrase exact dedup adapter to support `key_mode: "bbox"` so it can run **before** LLM refresh.
- Rationale: identical bbox in same image should represent the same region; requesting distinct phrases is counterproductive.

### Expected benefits / risks

**Benefits**

- Better disambiguation for highly-overlapping instances (model sees the set).
- Lower total request overhead (1 call per record vs per object), improving throughput.
- Enables robust post-validation using returned bbox.

**Risks**

- “Too many boxes” may harm recognition; mitigated by `draw_boxes=false` toggle.
- With `all_objects`, the model may try to disambiguate using spatial/ordinal language; mitigated by prompt constraints.
- Duplicate bboxes: mitigated by bbox-only dedup step before refresh.

