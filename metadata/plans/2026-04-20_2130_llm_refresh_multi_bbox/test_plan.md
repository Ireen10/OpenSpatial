## Test plan: LLM refresh multi-bbox mode

### Unit tests (pytest)

1) **All-objects single call updates multiple objects**
   - Given 2 objects + 1 multi-instance query with two candidates
   - Stub LLM returns:
     - index 1: phrase/category + echoed bbox
     - index 2: phrase/category + echoed bbox
   - Assert:
     - both objects updated
     - query_text rewritten as `"{p1}; {p2}"`
     - `aux.expression_refresh.n_llm_calls == 1`

2) **BBox echo mismatch is recorded**
   - Stub LLM returns a bbox different from the input for one index
   - Assert:
     - `aux.expression_refresh.errors` contains code `bbox_mismatch` with index/object_id context

3) **Draw boxes toggle does not break calling**
   - Run the same test with `draw_boxes=false`
   - Assert the request succeeds and output mapping still correct

4) **Dedup adapter bbox-only mode**
   - Construct metadata with two objects having identical `bbox_xyxy_norm_1000` but different phrase
   - Run `ObjectDedupExactAdapter(key_mode="bbox")`
   - Assert:
     - only one object kept
     - queries remapped and counts consistent

### Test commands

```bash
python -m pytest metadata/tests -q
```

