"""Training export: optional per-shard progress callback."""

from __future__ import annotations

from pathlib import Path

from openspatial_metadata.export.training_pack import export_training_bundles_from_metadata_qa


def test_on_shard_progress_called_once_per_metadata_qa_shard(tmp_path: Path) -> None:
    qa = tmp_path / "metadata_qa"
    qa.mkdir()
    (qa / "data_000000.jsonl").write_text("", encoding="utf-8")
    (qa / "data_000001.jsonl").write_text("", encoding="utf-8")
    bundle_root = tmp_path / "train_out"
    (bundle_root / "images").mkdir(parents=True)
    (bundle_root / "jsonl").mkdir(parents=True)

    seen: list[tuple[int, int, str]] = []

    def cb(si: int, n: int, p: Path) -> None:
        seen.append((si, n, p.name))

    n_bundles = export_training_bundles_from_metadata_qa(
        metadata_qa_dir=qa,
        bundle_root=bundle_root,
        image_root=tmp_path,
        rows_per_part=1024,
        row_align=1,
        on_shard_progress=cb,
    )
    assert n_bundles == 0
    assert seen == [(0, 2, "data_000000.jsonl"), (1, 2, "data_000001.jsonl")]
