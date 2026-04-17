# Generated artifacts (local only)

This directory is populated when you run either of the following from the **repository root**.

## Option A: script (recommended)

PowerShell:

```powershell
$env:PYTHONPATH = "metadata\src"
python metadata/scripts/generate_2d_spatial_relation_artifacts.py
```

Bash:

```bash
PYTHONPATH=metadata/src python metadata/scripts/generate_2d_spatial_relation_artifacts.py
```

## Option B: unit tests

After a successful run of `metadata.tests.test_spatial_relation_2d_annotation_task`, the same files are written if the environment variable is set:

PowerShell:

```powershell
$env:PYTHONPATH = "metadata\src"
$env:OPENSPATIAL_WRITE_2D_RELATION_ARTIFACTS = "1"
python -m unittest metadata.tests.test_spatial_relation_2d_annotation_task
```

## Output files

| File | Contents |
|------|----------|
| `dense_from_fixture.metadata.jsonl` | One line: enriched `MetadataV0` JSON (dense grounding fixture). |
| `dense_from_fixture.qa.jsonl` | One JSON object per line: `question`, `answer`, `meta`, etc. (no raw image bytes). |
| `dense_from_fixture.qa_preview.md` | Human-readable Q/A + meta for the same run. |
| `complex_from_fixture.*` | Same trio for the complex caption fixture. |

Generated `*.metadata.jsonl`, `*.qa.jsonl`, and `*.qa_preview.md` are listed in `.gitignore`; this `README.md` is tracked.
