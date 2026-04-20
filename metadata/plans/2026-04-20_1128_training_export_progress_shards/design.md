# Training export progress (shard-level) — design

## Goal

When `pipelines.export_training=true`, the **second stage** (packing training bundles from `metadata_qa/data_*.jsonl`) should also show progress.

- Progress granularity: **shard-level** (one tick per `metadata_qa/data_??????.jsonl`).
- Must integrate with existing CLI `--progress {tqdm,log,none}`.
- Must not change export outputs.

## Current behavior

- Stage 1 shows progress per input record.
- Stage 2 runs synchronously in `export/training_pack.py` and prints only occasional warnings and the final `training export ... wrote N bundle(s)` line, which can look like a hang.

## Design

### API shape

Add an **optional hook** to `export_training_bundles_from_metadata_qa`:

- `progress: Optional[Callable[[int, int, Path], None]]`
  - Called once per shard **right before** processing its lines.
  - Arguments: `(shard_index, shard_count, shard_path)`.

This keeps `training_pack.py` independent of CLI globals (`_PROGRESS_MODE`, `_tqdm`) and avoids circular imports.

### CLI integration

In `cli._finalize_training_export_for_split`:

- If `--progress tqdm`: create a local `tqdm(total=len(shards), desc=f"training {ds}/{split}")` and in the hook, update by 1 per shard.
- If `--progress log`: `_log(f"training export ... shard {i+1}/{n}: {shard_path.name}")`.
- If `--progress none`: pass `progress=None` (no output).

Also log one line at stage-2 start (unless progress=none), so users see the handoff.

### Non-goals

- No per-line (record) progress in stage 2.
- No parallelization changes.

## Compatibility

- Hook is optional and defaults to no-op → existing call sites unchanged.
- Output files unchanged.

## Status

Implemented: optional `on_shard_progress` on `export_training_bundles_from_metadata_qa` / `export_training_bundles_for_split`, wired from CLI `_finalize_training_export_for_split` with tqdm / log / none. Tests in `metadata/tests/test_training_export_shard_progress.py`.

