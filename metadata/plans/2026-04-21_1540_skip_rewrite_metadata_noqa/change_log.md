## Change log

### 2026-04-21

- **Behavior**: When running the training pipeline with `pipelines.to_metadata: false` (input already `MetadataV0`),
  the CLI no longer rewrites `metadata_noqa/` by default. It will only write `metadata_qa/` (when QA exists) and
  training bundles (when enabled).
- **Override**: Add `pipelines.persist_noqa: true` to force writing `metadata_noqa/` even when starting from metadata.
- **Templates**: E2E-B / E2E-C templates now set `pipelines.persist_noqa: false` explicitly.
- **Tests**: Updated E2E training pipeline tests for the new default; added coverage for `persist_noqa: true`.

