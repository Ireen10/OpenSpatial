## Test plan

### T1. Default behavior: raw start still writes metadata_noqa

- Run existing e2e tests that start from raw (e.g. `test_training_pipeline_cli_e2e.py::test_training_pipeline_cli_e2e`).
- Expect: `{split}/metadata_noqa/data_*.jsonl` exists and line-count matches input.

### T2. Default behavior: metadata start does NOT write metadata_noqa

- Add a new test based on existing CLI e2e harness:
  - Input: a MetadataV0 jsonl without `qa_items` (represents metadata_noqa input)
  - Config: `pipelines.to_metadata=false`, omit `persist_noqa`
  - Expect:
    - `{split}/metadata_noqa/` directory absent or empty
    - `{split}/metadata_qa/data_*.jsonl` exists (when QA generation produces items)
    - training export happens as usual

### T3. Explicit override: persist_noqa=true forces writing metadata_noqa even when to_metadata=false

- Similar setup to T2, but set `pipelines.persist_noqa: true`.
- Expect: `{split}/metadata_noqa/data_*.jsonl` exists and line-count equals input.

### T4. Template sanity

- Ensure templates (E2E-B/E2E-C) include `persist_noqa: false` and remain valid YAML.

### Commands

- `PYTHONPATH=metadata/src python -m pytest -q` (from repo root on CI) or
  from `metadata/`:
  - `PYTHONPATH=src python -m pytest -q`

