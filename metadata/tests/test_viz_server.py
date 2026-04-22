from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pytest

from openspatial_metadata.viz.config_index import build_dataset_index
from openspatial_metadata.viz.server import create_server, serve_forever

pytest.importorskip("PIL", reason="Pillow required for image fixture")


def _write_minimal_jpeg(path: Path, size: tuple[int, int] = (640, 426)) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(40, 80, 120)).save(path, format="JPEG", quality=85)


def test_viz_server_tree_record_image(tmp_path: Path) -> None:
    """End-to-end HTTP: tree, record line, image bytes."""
    image_root = tmp_path / "images"
    rel_img = Path("type7/train2014/COCO_train2014_000000569667.jpg")
    _write_minimal_jpeg(image_root / rel_img)

    out = tmp_path / "metadata_out"
    ds_name = "refcoco_grounding_aug_en_250618"
    split_name = "train_small"
    meta_dir = out / ds_name / split_name
    meta_dir.mkdir(parents=True)

    sample_path = "type7/train2014/COCO_train2014_000000569667.jpg"
    record = {
        "dataset": {"name": ds_name, "version": "v0", "split": split_name},
        "sample": {
            "sample_id": "type7-0806-6_myNGTNg5_2690",
            "view_id": 0,
            "image": {
                "path": sample_path.replace("\\", "/"),
                "width": 640,
                "height": 426,
                "coord_space": "norm_0_999",
                "coord_scale": 1000,
            },
        },
        "camera": None,
        "objects": [],
        "queries": [],
        "relations": [],
        "aux": {},
    }
    meta_file = meta_dir / "data_000000.jsonl"
    meta_file.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    cfg_dir = tmp_path / "configs" / "datasets" / "refcoco_grounding_aug_en_250618"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "dataset.yaml").write_text(
        "\n".join(
            [
                f"name: {ds_name}",
                "splits:",
                "  - name: train_small",
                "    input_type: jsonl",
                "    inputs: []",
                "viz:",
                "  mode: flat",
                f"  image_root: {image_root.as_posix()}",
            ]
        ),
        encoding="utf-8",
    )

    idx = build_dataset_index(tmp_path / "configs" / "datasets")
    httpd = create_server("127.0.0.1", 0, output_root=out, dataset_index=idx, default_scale=1000)
    real_port = httpd.server_address[1]

    t = threading.Thread(target=serve_forever, args=(httpd,), daemon=True)
    t.start()

    base = f"http://127.0.0.1:{real_port}"

    def get_json(url: str):
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    tree = get_json(f"{base}/api/tree")
    assert len(tree["files"]) == 1
    rel = tree["files"][0]["rel_path"]

    rec = get_json(f"{base}/api/record?path={quote(rel)}&line=0")
    assert rec["record"]["sample"]["sample_id"] == record["sample"]["sample_id"]

    img_url = f"{base}/api/image?dataset={ds_name}&relpath={quote(sample_path)}"
    with urllib.request.urlopen(img_url, timeout=5) as r:
        data = r.read()
        assert len(data) > 100
        assert data[:2] == b"\xff\xd8"

    seek = get_json(f"{base}/api/seek?path={quote(rel)}&sample_id=type7-0806-6_myNGTNg5_2690")
    assert seek["line"] == 0

    httpd.shutdown()


def test_viz_training_lines_with_optional_count(tmp_path: Path) -> None:
    ds_name = "demo_training_ds"
    split_name = "train"
    training_root = tmp_path / "training_out"
    jsonl_dir = training_root / ds_name / split_name / "jsonl"
    jsonl_dir.mkdir(parents=True)
    rows = [
        {"data": [{"role": "user", "content": [{"type": "text", "text": {"string": "q1"}}]}]},
        {"data": [{"role": "assistant", "content": [{"type": "text", "text": {"string": "a1"}}]}]},
        {"data": [{"role": "user", "content": [{"type": "text", "text": {"string": "q2"}}]}]},
    ]
    (jsonl_dir / "data_000000.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    cfg_dir = tmp_path / "configs" / "datasets" / ds_name
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "dataset.yaml").write_text(
        "\n".join(
            [
                f"name: {ds_name}",
                f"training_output_root: {training_root.as_posix()}",
                "splits:",
                f"  - name: {split_name}",
                "    input_type: jsonl",
                "    inputs: []",
            ]
        ),
        encoding="utf-8",
    )

    idx = build_dataset_index(tmp_path / "configs" / "datasets")
    httpd = create_server("127.0.0.1", 0, output_root=tmp_path / "metadata_out", dataset_index=idx, default_scale=1000)
    real_port = httpd.server_address[1]
    t = threading.Thread(target=serve_forever, args=(httpd,), daemon=True)
    t.start()
    base = f"http://127.0.0.1:{real_port}"

    def get_json(url: str):
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    r0 = get_json(
        f"{base}/api/training_lines?dataset={quote(ds_name)}&split={quote(split_name)}&part=0&offset=0&limit=2"
    )
    assert len(r0["records"]) == 2
    assert r0["has_more"] is True
    assert "line_count" not in r0

    r1 = get_json(
        f"{base}/api/training_lines?dataset={quote(ds_name)}&split={quote(split_name)}&part=0&offset=0&limit=2&with_count=true"
    )
    assert len(r1["records"]) == 2
    assert r1["has_more"] is True
    assert r1["line_count"] == 3

    httpd.shutdown()


def test_viz_server_tree_with_dataset_specific_metadata_root(tmp_path: Path) -> None:
    """
    Dataset may set metadata_output_root to a dataset-specific directory.
    In this layout files are under {root}/{split}/..., not {root}/{dataset}/{split}/...
    """
    ds_name = "demo_ds_specific_root"
    split_name = "train"
    ds_root = tmp_path / "ds_specific_root"
    meta_dir = ds_root / split_name / "metadata_noqa"
    meta_dir.mkdir(parents=True)
    rec = {
        "dataset": {"name": ds_name, "version": "v0", "split": split_name},
        "sample": {
            "sample_id": "s-1",
            "view_id": 0,
            "image": {"path": "dummy.jpg", "width": 4, "height": 4, "coord_space": "norm_0_999", "coord_scale": 1000},
        },
        "camera": None,
        "objects": [],
        "queries": [],
        "relations": [],
        "aux": {},
    }
    (meta_dir / "data_000000.jsonl").write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")

    cfg_dir = tmp_path / "configs" / "datasets" / ds_name
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "dataset.yaml").write_text(
        "\n".join(
            [
                f"name: {ds_name}",
                f"metadata_output_root: {ds_root.as_posix()}",
                "splits:",
                f"  - name: {split_name}",
                "    input_type: jsonl",
                "    inputs: []",
            ]
        ),
        encoding="utf-8",
    )

    idx = build_dataset_index(tmp_path / "configs" / "datasets")
    httpd = create_server("127.0.0.1", 0, output_root=tmp_path / "unused_root", dataset_index=idx, default_scale=1000)
    real_port = httpd.server_address[1]
    t = threading.Thread(target=serve_forever, args=(httpd,), daemon=True)
    t.start()
    base = f"http://127.0.0.1:{real_port}"

    def get_json(url: str):
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    tree = get_json(f"{base}/api/tree")
    assert len(tree["files"]) == 1
    f0 = tree["files"][0]
    assert f0["dataset_dir"] == ds_name
    assert f0["split"] == split_name
    assert f0["stage"] == "metadata_noqa"

    rel = f0["rel_path"]
    one = get_json(f"{base}/api/record?dataset={quote(ds_name)}&path={quote(rel)}&line=0")
    assert one["record"]["sample"]["sample_id"] == "s-1"

    httpd.shutdown()
