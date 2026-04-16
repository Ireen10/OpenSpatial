from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from openspatial_metadata.viz.config_index import (
    build_dataset_index,
    image_root_for_dataset,
    resolved_image_root,
)


def test_build_dataset_index_two_configs(tmp_path: Path) -> None:
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    (d1 / "dataset.yaml").write_text(
        textwrap.dedent(
            """
            name: ds_a
            splits:
              - name: s
                input_type: jsonl
                inputs: []
            viz:
              mode: flat
              image_root: /tmp/img_a
            """
        ).strip(),
        encoding="utf-8",
    )
    (d2 / "dataset.yaml").write_text(
        textwrap.dedent(
            """
            name: ds_b
            splits:
              - name: s
                input_type: jsonl
                inputs: []
            """
        ).strip(),
        encoding="utf-8",
    )
    idx = build_dataset_index(tmp_path)
    assert set(idx.keys()) == {"ds_a", "ds_b"}
    assert image_root_for_dataset(idx, "ds_a") == "/tmp/img_a"
    assert image_root_for_dataset(idx, "ds_b") is None


def test_resolved_image_root_relative_to_yaml(tmp_path: Path) -> None:
    ds_dir = tmp_path / "my_ds"
    ds_dir.mkdir(parents=True)
    images = tmp_path / "images_root"
    images.mkdir()
    marker = images / "a.jpg"
    marker.write_bytes(b"x")
    (ds_dir / "dataset.yaml").write_text(
        textwrap.dedent(
            f"""
            name: rel_ds
            splits:
              - name: s
                input_type: jsonl
                inputs: []
            viz:
              mode: flat
              image_root: ../images_root
            """
        ).strip(),
        encoding="utf-8",
    )
    idx = build_dataset_index(tmp_path)
    r = resolved_image_root(idx, "rel_ds")
    assert r == images.resolve()
