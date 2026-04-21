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
    md_qa = out_root / "metadata" / "demo_metadata_to_training" / "train_small" / "metadata_qa"
    assert (md_qa / "data_000000.jsonl").is_file()

    train_root = out_root / "training"
    tar = train_root / "demo_metadata_to_training" / "train_small" / "images" / "data_000000.tar"
    tarinfo = train_root / "demo_metadata_to_training" / "train_small" / "images" / "data_000000_tarinfo.json"
    jsonl = train_root / "demo_metadata_to_training" / "train_small" / "jsonl" / "data_000000.jsonl"
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


@pytest.mark.e2e
def test_training_pipeline_writes_noqa_when_ensure_qa_produces_no_items(tmp_path: Path) -> None:
    """If ensure_qa is on and QA generation yields 0 items for a line: skip metadata_qa/export for that line (default: no metadata_noqa copy when to_metadata=false)."""
    from PIL import Image

    rel = Path("type7/train2014/COCO_train2014_000000569667.jpg")
    img_path = Path("metadata/tests/fixtures/images") / rel
    img_path.parent.mkdir(parents=True, exist_ok=True)
    if not img_path.exists():
        Image.new("RGB", (640, 426), color=(120, 160, 200)).save(img_path, format="JPEG", quality=90)

    fixture_path = Path("metadata/tests/fixtures/generated/spatial_relation_2d/dense_from_fixture.metadata.jsonl")
    good = json.loads(fixture_path.read_text(encoding="utf-8").splitlines()[0])
    empty_rel = json.loads(json.dumps(good))
    empty_rel["relations"] = []
    empty_rel["qa_items"] = []

    in_jsonl = tmp_path / "mixed.metadata.jsonl"
    in_jsonl.write_text(
        json.dumps(empty_rel, ensure_ascii=False) + "\n" + json.dumps(good, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    out_root = tmp_path / "out"
    ds_dir = tmp_path / "datasets" / "demo_mixed_qa"
    ds_dir.mkdir(parents=True, exist_ok=True)
    (ds_dir / "dataset.yaml").write_text(
        "\n".join(
            [
                'name: "demo_mixed_qa"',
                f'metadata_output_root: "{(out_root / "metadata").as_posix()}"',
                f'training_output_root: "{(out_root / "training").as_posix()}"',
                "viz:",
                '  image_root: "metadata/tests/fixtures/images"',
                "splits:",
                '  - name: "train_small"',
                '    input_type: "jsonl"',
                "    inputs:",
                f'      - "{in_jsonl.as_posix()}"',
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

    md_qa = out_root / "metadata" / "demo_mixed_qa" / "train_small" / "metadata_qa" / "data_000000.jsonl"
    train_jsonl = out_root / "training" / "demo_mixed_qa" / "train_small" / "jsonl" / "data_000000.jsonl"

    n_qa = sum(1 for _ in md_qa.read_text(encoding="utf-8").splitlines() if _.strip())
    n_train = sum(1 for _ in train_jsonl.read_text(encoding="utf-8").splitlines() if _.strip())
    assert n_qa == 1
    assert n_train == 1


@pytest.mark.e2e
def test_training_pipeline_raw_start_skips_metadata_noqa_when_persist_noqa_false(tmp_path: Path) -> None:
    """Upstream/raw path (to_metadata=true) can omit metadata_noqa on disk when persist_noqa=false."""
    from PIL import Image

    rel = Path("type7/train2014/COCO_train2014_000000569667.jpg")
    img_path = Path("metadata/tests/fixtures/images") / rel
    img_path.parent.mkdir(parents=True, exist_ok=True)
    if not img_path.exists():
        Image.new("RGB", (640, 426), color=(120, 160, 200)).save(img_path, format="JPEG", quality=90)

    out_root = tmp_path / "out"
    ds_dir = tmp_path / "datasets" / "demo_raw_skip_noqa"
    ds_dir.mkdir(parents=True, exist_ok=True)
    (ds_dir / "dataset.yaml").write_text(
        "\n".join(
            [
                'name: "demo_raw_skip_noqa"',
                f'metadata_output_root: "{(out_root / "metadata").as_posix()}"',
                f'training_output_root: "{(out_root / "training").as_posix()}"',
                "viz:",
                '  image_root: "metadata/tests/fixtures/images"',
                "adapters:",
                "  - file_name: passthrough",
                "    class_name: PassthroughAdapter",
                "splits:",
                '  - name: "train_small"',
                '    input_type: "jsonl"',
                "    inputs:",
                '      - "metadata/tests/fixtures/generated/spatial_relation_2d/dense_from_fixture.metadata.jsonl"',
                "pipelines:",
                "  to_metadata: true",
                "  persist_noqa: false",
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

    md_noqa_dir = out_root / "metadata" / "demo_raw_skip_noqa" / "train_small" / "metadata_noqa"
    assert not (md_noqa_dir / "data_000000.jsonl").is_file()
    md_qa = out_root / "metadata" / "demo_raw_skip_noqa" / "train_small" / "metadata_qa" / "data_000000.jsonl"
    assert md_qa.is_file()
    assert (out_root / "training" / "demo_raw_skip_noqa" / "train_small" / "jsonl" / "data_000000.jsonl").is_file()


@pytest.mark.e2e
def test_training_pipeline_persist_noqa_true_forces_noqa_write(tmp_path: Path) -> None:
    """Even when to_metadata=false, persist_noqa=true should write metadata_noqa shard."""
    from PIL import Image

    rel = Path("type7/train2014/COCO_train2014_000000569667.jpg")
    img_path = Path("metadata/tests/fixtures/images") / rel
    img_path.parent.mkdir(parents=True, exist_ok=True)
    if not img_path.exists():
        Image.new("RGB", (640, 426), color=(120, 160, 200)).save(img_path, format="JPEG", quality=90)

    fixture_path = Path("metadata/tests/fixtures/generated/spatial_relation_2d/dense_from_fixture.metadata.jsonl")
    in_jsonl = tmp_path / "one.metadata.jsonl"
    in_jsonl.write_text(fixture_path.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")

    out_root = tmp_path / "out"
    ds_dir = tmp_path / "datasets" / "demo_force_noqa"
    ds_dir.mkdir(parents=True, exist_ok=True)
    (ds_dir / "dataset.yaml").write_text(
        "\n".join(
            [
                'name: "demo_force_noqa"',
                f'metadata_output_root: "{(out_root / "metadata").as_posix()}"',
                f'training_output_root: "{(out_root / "training").as_posix()}"',
                "viz:",
                '  image_root: "metadata/tests/fixtures/images"',
                "splits:",
                '  - name: "train_small"',
                '    input_type: "jsonl"',
                "    inputs:",
                f'      - "{in_jsonl.as_posix()}"',
                "pipelines:",
                "  to_metadata: false",
                "  persist_noqa: true",
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

    md_noqa = out_root / "metadata" / "demo_force_noqa" / "train_small" / "metadata_noqa" / "data_000000.jsonl"
    assert md_noqa.is_file()
    n_noqa = sum(1 for _ in md_noqa.read_text(encoding="utf-8").splitlines() if _.strip())
    assert n_noqa == 1


@pytest.mark.e2e
def test_training_pipeline_multi_bundle_from_duplicated_jsonl(tmp_path: Path) -> None:
    """
    Same spatial_relation_2d line repeated N times -> N training rows (one visual group per record).
    With training_rows_per_part: 1, export_training emits N bundles: data_000000 .. data_{N-1}.
    """
    from PIL import Image

    rel = Path("type7/train2014/COCO_train2014_000000569667.jpg")
    img_path = Path("metadata/tests/fixtures/images") / rel
    img_path.parent.mkdir(parents=True, exist_ok=True)
    if not img_path.exists():
        Image.new("RGB", (640, 426), color=(120, 160, 200)).save(img_path, format="JPEG", quality=90)

    fixture_path = Path("metadata/tests/fixtures/generated/spatial_relation_2d/dense_from_fixture.metadata.jsonl")
    line = fixture_path.read_text(encoding="utf-8").splitlines()[0]
    n = 4
    in_jsonl = tmp_path / "dense_x4.metadata.jsonl"
    in_jsonl.write_text("\n".join([line] * n) + "\n", encoding="utf-8")

    out_root = tmp_path / "out"
    ds_dir = tmp_path / "datasets" / "demo_multi_bundle"
    ds_dir.mkdir(parents=True, exist_ok=True)
    (ds_dir / "dataset.yaml").write_text(
        "\n".join(
            [
                'name: "demo_multi_bundle"',
                f'metadata_output_root: "{(out_root / "metadata").as_posix()}"',
                f'training_output_root: "{(out_root / "training").as_posix()}"',
                "viz:",
                '  image_root: "metadata/tests/fixtures/images"',
                "splits:",
                '  - name: "train_small"',
                '    input_type: "jsonl"',
                "    inputs:",
                f'      - "{in_jsonl.as_posix()}"',
                "pipelines:",
                "  to_metadata: false",
                "  ensure_qa: true",
                "  export_training: true",
                '  qa_task_name: "spatial_relation_2d"',
                "  training_rows_per_part: 1",
                "  training_row_align: 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    from openspatial_metadata.cli import main

    gcfg = "metadata/tests/configs/e2e_training_pipeline/global.yaml"
    qcfg = "metadata/tests/configs/e2e_training_pipeline/qa_tasks.yaml"
    main(["--config-root", str(ds_dir.parent), "--global-config", gcfg, "--qa-config", qcfg, "--progress", "none"])

    train_base = out_root / "training" / "demo_multi_bundle" / "train_small"
    jl_dir = train_base / "jsonl"
    img_dir = train_base / "images"
    expected = [f"data_{i:06d}.jsonl" for i in range(n)]
    assert sorted(p.name for p in jl_dir.glob("data_*.jsonl")) == expected
    assert sorted(p.name for p in img_dir.glob("data_*.tar")) == [f"data_{i:06d}.tar" for i in range(n)]
    assert sorted(p.name for p in img_dir.glob("data_*_tarinfo.json")) == [
        f"data_{i:06d}_tarinfo.json" for i in range(n)
    ]

    total_lines = 0
    for name in expected:
        total_lines += sum(1 for _ in (jl_dir / name).read_text(encoding="utf-8").splitlines() if _.strip())
    assert total_lines == n

