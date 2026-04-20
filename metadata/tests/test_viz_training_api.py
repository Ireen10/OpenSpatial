from __future__ import annotations

import json
from pathlib import Path


def test_viz_training_tar_slice_read() -> None:
    """
    Verify we can read a training image from tar without extraction,
    using tarinfo offset_data/size.
    """
    tar = Path("metadata/tests/.tmp_pipeline_out/training/demo_metadata_to_training/train_small/images/data_000000.tar")
    tarinfo = Path(
        "metadata/tests/.tmp_pipeline_out/training/demo_metadata_to_training/train_small/images/data_000000_tarinfo.json"
    )
    # This test is optional when artifacts don't exist; skip if user didn't run pipeline.
    if not tar.is_file() or not tarinfo.is_file():
        return

    idx = json.loads(tarinfo.read_text(encoding="utf-8"))
    # pick first member
    (name, meta) = next(iter(idx.items()))
    from openspatial_metadata.viz.paths import read_tar_member_by_tarinfo

    data = read_tar_member_by_tarinfo(tar, offset_data=int(meta["offset_data"]), size=int(meta["size"]))
    assert data[:2] == b"\xff\xd8"  # JPEG SOI

