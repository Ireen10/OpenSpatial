from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_training_pipeline_cli_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    End-to-end:
    metadata(without qa_items) jsonl -> ensure_qa -> export_training bundle (tar+tarinfo+jsonl)
    """
    # Ensure output root is isolated
    out_root = tmp_path / "out"
    # Provide a real image at sample.image.path under fixtures image_root.
    from PIL import Image

    rel = Path("type7/train2014/COCO_train2014_000000569667.jpg")
    img_path = Path("metadata/tests/fixtures/images") / rel
    img_path.parent.mkdir(parents=True, exist_ok=True)
    if not img_path.exists():
        Image.new("RGB", (640, 426), color=(120, 160, 200)).save(img_path, format="JPEG", quality=90)

    # Build a temp config set so both metadata + training roots are isolated.
    ds_dir = tmp_path / "datasets" / "demo_metadata_to_training"
    ds_dir.mkdir(parents=True, exist_ok=True)
    ds_yaml = ds_dir / "dataset.yaml"
    ds_yaml.write_text(
        "\n".join(
            [
                'name: "demo_metadata_to_training"',
                f'metadata_output_root: "{(out_root / "metadata").as_posix()}"',
                f'training_output_root: "{(out_root / "training").as_posix()}"',
                "viz:",
                '  image_root: "metadata/tests/fixtures/images"',
                "splits:",
                '  - name: "train_small"',
                '    input_type: "jsonl"',
                "    inputs:",
                '      - "metadata/tests/fixtures/generated/spatial_relation_2d/dense_from_fixture.metadata.jsonl"',
                "pipelines:",
                "  to_metadata: false",
                "  ensure_qa: true",
                "  export_training: true",
                '  qa_task_name: "spatial_relation_2d"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    from openspatial_metadata.cli import main

    gcfg = "metadata/tests/configs/e2e_training_pipeline/global.yaml"
    qcfg = "metadata/tests/configs/e2e_training_pipeline/qa_tasks.yaml"
    main(["--config-root", str(ds_dir.parent), "--global-config", gcfg, "--qa-config", qcfg, "--progress", "none"])

    # Validate outputs exist.
    md_noqa = out_root / "metadata" / "demo_metadata_to_training" / "train_small" / "metadata_noqa"
    md_qa = out_root / "metadata" / "demo_metadata_to_training" / "train_small" / "metadata_qa"
    assert (md_noqa / "dense_from_fixture.metadata.jsonl").is_file()
    assert (md_qa / "dense_from_fixture.metadata.jsonl").is_file()

    train_root = out_root / "training"
    tar = train_root / "demo_metadata_to_training" / "train_small" / "images" / "part_000000.tar"
    tarinfo = train_root / "demo_metadata_to_training" / "train_small" / "images" / "part_000000_tarinfo.json"
    jsonl = train_root / "demo_metadata_to_training" / "train_small" / "jsonl" / "part_000000.jsonl"
    assert tar.is_file()
    assert tarinfo.is_file()
    assert jsonl.is_file()

    # Basic schema check: tarinfo keys match jsonl relative_path(s).
    idx = json.loads(tarinfo.read_text(encoding="utf-8"))
    lines = [json.loads(x) for x in jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert lines, "expected at least one training row"
    relpaths = [ln["data"][0]["content"][0]["image"]["relative_path"] for ln in lines]
    for rp in relpaths:
        assert rp in idx

