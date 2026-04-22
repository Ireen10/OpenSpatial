from __future__ import annotations

import json
from pathlib import Path

from openspatial_metadata.viz.paths import (
    count_lines_jsonl,
    enumerate_metadata_jsonl,
    enumerate_training_parts_for_dataset,
    find_sample_line,
    read_line_jsonl,
    safe_file_under_root,
)


def test_enumerate_skips_checkpoints_and_nested(tmp_path: Path) -> None:
    root = tmp_path / "out"
    (root / "ds" / "sp").mkdir(parents=True)
    (root / "ds" / "sp" / "a.metadata.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "ds" / "sp" / ".checkpoints").mkdir()
    (root / "ds" / "sp" / ".checkpoints" / "x.json").write_text("{}", encoding="utf-8")
    # nested extra dir under split — should be included (metadata_noqa/metadata_qa).
    (root / "ds" / "sp" / "extra").mkdir()
    (root / "ds" / "sp" / "extra" / "b.metadata.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "ds" / "sp" / "data_000000.jsonl").write_text("{}\n", encoding="utf-8")
    files = enumerate_metadata_jsonl(root)
    assert len(files) == 3
    names = sorted([f["name"] for f in files])
    assert names == ["a.metadata.jsonl", "b.metadata.jsonl", "data_000000.jsonl"]


def test_read_line_and_find_sample(tmp_path: Path) -> None:
    p = tmp_path / "f.metadata.jsonl"
    rows = [
        {"sample": {"sample_id": "a"}},
        {"sample": {"sample_id": "b"}},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert read_line_jsonl(p, 0)["sample"]["sample_id"] == "a"
    assert read_line_jsonl(p, 1)["sample"]["sample_id"] == "b"
    assert find_sample_line(p, "b") == 1


def test_safe_file_under_root(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    f = root / "sub" / "a.jpg"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x")
    assert safe_file_under_root(f, root) == f.resolve()
    assert safe_file_under_root(tmp_path / "other", root) is None


def test_count_lines_jsonl_updates_after_file_change(tmp_path: Path) -> None:
    p = tmp_path / "rows.jsonl"
    p.write_text("{}\n{}\n", encoding="utf-8")
    assert count_lines_jsonl(p) == 2
    # second call should be cached and stable
    assert count_lines_jsonl(p) == 2
    p.write_text("{}\n{}\n{}\n", encoding="utf-8")
    assert count_lines_jsonl(p) == 3


def test_enumerate_training_parts_for_dataset_only_target(tmp_path: Path) -> None:
    root = tmp_path / "training_out"
    # target dataset
    (root / "ds_a" / "train" / "jsonl").mkdir(parents=True)
    (root / "ds_a" / "train" / "images").mkdir(parents=True)
    (root / "ds_a" / "train" / "jsonl" / "data_000000.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "ds_a" / "train" / "images" / "data_000000.tar").write_bytes(b"x")
    (root / "ds_a" / "train" / "images" / "data_000000_tarinfo.json").write_text("{}", encoding="utf-8")
    # unrelated dataset
    (root / "ds_b" / "train" / "jsonl").mkdir(parents=True)
    (root / "ds_b" / "train" / "images").mkdir(parents=True)
    (root / "ds_b" / "train" / "jsonl" / "data_000000.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "ds_b" / "train" / "images" / "data_000000.tar").write_bytes(b"x")
    (root / "ds_b" / "train" / "images" / "data_000000_tarinfo.json").write_text("{}", encoding="utf-8")

    parts = enumerate_training_parts_for_dataset(root, "ds_a")
    assert len(parts) == 1
    assert parts[0]["dataset"] == "ds_a"
