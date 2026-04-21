## Execution plan

### Config/schema changes

- Extend dataset config `pipelines` to accept `persist_noqa: Optional[bool]`.
- Define an internal helper in `openspatial_metadata.cli` to compute the effective `persist_noqa`:
  - if user sets it explicitly, use it
  - else default to `to_metadata` (write `metadata_noqa` only when we actually generated metadata in this run)

### CLI behavior changes

- In `_process_jsonl_file_training_pipeline`:
  - Only open/write `metadata_noqa/data_*.jsonl` when effective `persist_noqa` is true.
  - Keep checkpoint semantics identical (per input file + `next_input_index`), independent of `metadata_noqa` writing.
  - Keep `metadata_qa` writing behavior unchanged (write only when `qa_items` non-empty).
- In training-export finalization for a split:
  - Continue to read from `{split}/metadata_qa/data_*.jsonl` only (current behavior).
  - If `metadata_qa` doesn’t exist (no QA items), export remains skipped as today.

### Templates/docs

- Update `metadata/templates/configs_minimal/datasets/e2e_b_from_metadata_noqa/dataset.yaml` and
  `.../e2e_c_from_metadata_withqa/dataset.yaml` to set:
  - `pipelines.to_metadata: false`
  - `pipelines.persist_noqa: false` (explicit, so behavior is stable and obvious)
- Optionally (separately) update `metadata/docs/config_yaml_zh.md` to document `persist_noqa` semantics.

## Rollout / safety

- Preserve previous behavior for raw-start datasets (E2E-A / E2E-D) by default (`to_metadata: true` ⇒ `metadata_noqa` still written).
- Provide an escape hatch for users who still want `metadata_noqa` output even when starting from metadata (`persist_noqa: true`).

