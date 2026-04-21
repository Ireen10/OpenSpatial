"""Training export reading RGB from per-shard ``.tar`` (``split.image_archive_pattern``)."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest
from PIL import Image

from openspatial_metadata.export.training_pack import export_training_bundles_from_metadata_qa
from openspatial_metadata.io.image_archive import resolve_image_archive_path


def test_resolve_image_archive_path_format(tmp_path: Path) -> None:
    p = resolve_image_archive_path("archives/part_{shard:06d}.tar", 7, tmp_path)
    assert p.name == "part_000007.tar"
    assert "archives" in p.parts


def test_training_export_reads_image_from_shard_tar(tmp_path: Path) -> None:
    img = Image.new("RGB", (32, 24), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    archives = tmp_path / "archives"
    archives.mkdir()
    tar_p = archives / "part_000000.tar"
    with tarfile.open(tar_p, "w") as tf:
        ti = tarfile.TarInfo(name="sample/c0.png")
        ti.size = len(png_bytes)
        tf.addfile(ti, io.BytesIO(png_bytes))

    qa = tmp_path / "metadata_qa"
    qa.mkdir()
    md_line = {
        "dataset": {"name": "t", "version": "v0", "split": "train"},
        "sample": {
            "sample_id": "s1",
            "image": {"path": "sample/c0.png", "coord_scale": 1000},
        },
        "objects": [],
        "relations": [],
        "qa_items": [
            {
                "qa_id": "qa#0",
                "task": "spatial_relation_2d",
                "question": "q",
                "answer": "left",
                "question_type": "open_ended",
                "question_tags": [],
                "meta": {
                    "marked_roles": [],
                    "mark_colors": {},
                    "n_marked_boxes": 0,
                    "instruction_mode": "none",
                    "answer_mode": "short_phrase",
                },
            }
        ],
        "aux": {"record_ref": {"input_file": "x.jsonl", "input_index": 0}},
    }
    (qa / "data_000000.jsonl").write_text(json.dumps(md_line, ensure_ascii=False) + "\n", encoding="utf-8")

    bundle_root = tmp_path / "train_out"
    (bundle_root / "images").mkdir(parents=True)
    (bundle_root / "jsonl").mkdir(parents=True)

    n = export_training_bundles_from_metadata_qa(
        metadata_qa_dir=qa,
        bundle_root=bundle_root,
        rows_per_part=1024,
        row_align=1,
        image_archive_pattern="archives/part_{shard:06d}.tar",
        image_archive_base_dir=str(tmp_path),
    )
    assert n == 1
    assert (bundle_root / "images" / "data_000000.tar").is_file()


@pytest.mark.parametrize("bad", ["", None])
def test_training_export_requires_base_when_pattern_set(tmp_path: Path, bad: str | None) -> None:
    with pytest.raises(ValueError, match="image_archive_base_dir"):
        export_training_bundles_from_metadata_qa(
            metadata_qa_dir=tmp_path,
            bundle_root=tmp_path,
            rows_per_part=8,
            row_align=1,
            image_archive_pattern="x_{shard:06d}.tar",
            image_archive_base_dir=bad,
        )
