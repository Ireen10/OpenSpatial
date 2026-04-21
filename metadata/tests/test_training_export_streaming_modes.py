from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from openspatial_metadata.export.training_pack import export_training_bundles_from_metadata_qa


def _write_sample_image(root: Path) -> str:
    rel = "sample/c0.png"
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 24), color=(20, 30, 40)).save(p, format="PNG")
    return rel


def _write_metadata_qa(path: Path, *, n_rows: int, image_rel: str) -> None:
    lines = []
    for i in range(n_rows):
        lines.append(
            {
                "dataset": {"name": "t", "version": "v0", "split": "train"},
                "sample": {
                    "sample_id": f"s{i}",
                    "image": {"path": image_rel, "coord_scale": 1000},
                },
                "objects": [],
                "relations": [],
                "qa_items": [
                    {
                        "qa_id": "qa#0",
                        "task": "spatial_relation_2d",
                        "question": f"q{i}",
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
                "aux": {"record_ref": {"input_file": "x.jsonl", "input_index": i}},
            }
        )
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")


def _read_all_jsonl_rows(bundle_root: Path) -> list[dict]:
    out = []
    for p in sorted((bundle_root / "jsonl").glob("data_*.jsonl")):
        out.extend([json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()])
    return out


def test_training_export_streaming_and_legacy_modes_are_row_equivalent(tmp_path: Path) -> None:
    image_root = tmp_path / "images"
    image_rel = _write_sample_image(image_root)
    qa_dir = tmp_path / "metadata_qa"
    qa_dir.mkdir()
    _write_metadata_qa(qa_dir / "data_000000.jsonl", n_rows=5, image_rel=image_rel)

    out_stream = tmp_path / "out_stream"
    out_legacy = tmp_path / "out_legacy"
    (out_stream / "images").mkdir(parents=True)
    (out_stream / "jsonl").mkdir(parents=True)
    (out_legacy / "images").mkdir(parents=True)
    (out_legacy / "jsonl").mkdir(parents=True)

    n_stream = export_training_bundles_from_metadata_qa(
        metadata_qa_dir=qa_dir,
        bundle_root=out_stream,
        image_root=image_root,
        rows_per_part=2,
        row_align=1,
        pipeline_streaming_enabled=True,
        training_remainder_mode="drop",
    )
    n_legacy = export_training_bundles_from_metadata_qa(
        metadata_qa_dir=qa_dir,
        bundle_root=out_legacy,
        image_root=image_root,
        rows_per_part=2,
        row_align=1,
        pipeline_streaming_enabled=False,
        training_remainder_mode="drop",
    )

    assert n_stream == n_legacy == 3
    rows_stream = _read_all_jsonl_rows(out_stream)
    rows_legacy = _read_all_jsonl_rows(out_legacy)
    assert len(rows_stream) == len(rows_legacy) == 5


def test_training_export_drop_mode_discards_unaligned_remainder(tmp_path: Path) -> None:
    image_root = tmp_path / "images"
    image_rel = _write_sample_image(image_root)
    qa_dir = tmp_path / "metadata_qa"
    qa_dir.mkdir()
    _write_metadata_qa(qa_dir / "data_000000.jsonl", n_rows=5, image_rel=image_rel)

    bundle_root = tmp_path / "out"
    (bundle_root / "images").mkdir(parents=True)
    (bundle_root / "jsonl").mkdir(parents=True)

    n = export_training_bundles_from_metadata_qa(
        metadata_qa_dir=qa_dir,
        bundle_root=bundle_root,
        image_root=image_root,
        rows_per_part=4,
        row_align=4,
        pipeline_streaming_enabled=True,
        training_remainder_mode="drop",
    )
    rows = _read_all_jsonl_rows(bundle_root)
    assert n == 1
    assert len(rows) == 4
    assert not (bundle_root / "jsonl" / "remainder_rows.jsonl").exists()
