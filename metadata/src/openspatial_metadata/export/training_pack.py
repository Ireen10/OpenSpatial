"""
Pack training bundles from ``metadata_qa/data_*.jsonl`` shards.

Rows are accumulated in global order (shard index, then line order) and split into
``data_{bundle_id:06d}.{tar,jsonl}`` with ``training_rows_per_part`` rows per bundle,
with the final remainder trimmed to a multiple of ``training_row_align`` (when align > 1).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from openspatial_metadata.export.paths import disambiguate_relpath
from openspatial_metadata.export.run import build_training_members_and_rows
from openspatial_metadata.export.stream import TrainingBundleWriter, bundle_paths
from openspatial_metadata.schema.metadata_v0 import MetadataV0

_SHARD_RE = re.compile(r"^data_(\d{6})\.jsonl$")


def _sorted_metadata_qa_shards(qa_dir: Path) -> List[Path]:
    shards: List[Tuple[int, Path]] = []
    for p in qa_dir.glob("data_*.jsonl"):
        m = _SHARD_RE.match(p.name)
        if not m:
            continue
        shards.append((int(m.group(1)), p))
    shards.sort(key=lambda x: x[0])
    return [p for _, p in shards]


def _clear_existing_training_bundles(bundle_root: Path) -> None:
    """Remove previous ``data_*`` training outputs under images/ and jsonl/."""
    images = bundle_root / "images"
    jsonl = bundle_root / "jsonl"
    for d in (images, jsonl):
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if not p.is_file():
                continue
            n = p.name
            if n.startswith("data_") and (n.endswith(".tar") or n.endswith(".jsonl") or "_tarinfo.json" in n):
                try:
                    p.unlink()
                except OSError:
                    pass


def _write_one_bundle(
    bundle_root: Path,
    bundle_id: int,
    items: List[Tuple[str, bytes, Dict[str, Any], int]],
) -> None:
    paths = bundle_paths(bundle_root, bundle_id)
    with TrainingBundleWriter(paths, resume=False) as bw:
        for rel, data, row, input_index in items:
            rel2 = disambiguate_relpath(rel, input_index=input_index, existing=bw.existing_names)
            bw.add_image(rel2, data)
            row["data"][0]["content"][0]["image"]["relative_path"] = rel2
            bw.add_jsonl_row(row)
        bw.finalize_tarinfo()


def export_training_bundles_from_metadata_qa(
    *,
    metadata_qa_dir: Path,
    bundle_root: Path,
    image_root: Union[str, Path],
    rows_per_part: int,
    row_align: int,
    on_shard_progress: Optional[Callable[[int, int, Path], None]] = None,
) -> int:
    """
    Read all ``data_*.jsonl`` in ``metadata_qa_dir`` (numeric order), emit training bundles under
    ``bundle_root`` (``images/``, ``jsonl/``) as ``data_{id:06d}.*``.

    Returns the number of bundles written.
    """
    if rows_per_part <= 0:
        raise ValueError("rows_per_part must be positive")
    if row_align <= 0:
        raise ValueError("row_align must be positive")
    if rows_per_part % row_align != 0:
        raise ValueError(f"rows_per_part ({rows_per_part}) must be a multiple of row_align ({row_align})")

    shards = _sorted_metadata_qa_shards(metadata_qa_dir)
    if not shards:
        return 0

    n_shards = len(shards)
    buffer: List[Tuple[str, bytes, Dict[str, Any], int]] = []
    bundle_id = 0
    image_root = Path(image_root)

    def emit_chunk(n: int) -> None:
        nonlocal bundle_id, buffer
        if n <= 0 or len(buffer) < n:
            return
        chunk = buffer[:n]
        buffer = buffer[n:]
        _write_one_bundle(bundle_root, bundle_id, chunk)
        bundle_id += 1

    for si, shard_path in enumerate(shards):
        if on_shard_progress is not None:
            on_shard_progress(si, n_shards, shard_path)
        with shard_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                md = MetadataV0.parse_obj(payload)
                if not md.qa_items:
                    continue
                ref = (md.aux or {}).get("record_ref") or {}
                input_index = int(ref.get("input_index", 0))
                members, rows = build_training_members_and_rows(md, image_root=image_root)
                for (rel, data), row in zip(members, rows):
                    buffer.append((rel, data, row, input_index))
                while len(buffer) >= rows_per_part:
                    emit_chunk(rows_per_part)

    # Final remainder: trim to a multiple of row_align
    R = len(buffer)
    if R == 0:
        return bundle_id
    usable = (R // row_align) * row_align if row_align > 1 else R
    if usable == 0:
        print(
            f"[openspatial-metadata] training export: dropped {R} trailing row(s) "
            f"(not a multiple of row_align={row_align}); increase data or lower row_align.",
            file=sys.stderr,
        )
        buffer.clear()
        return bundle_id
    if usable < R:
        print(
            f"[openspatial-metadata] training export: dropped {R - usable} trailing row(s) "
            f"to satisfy row_align={row_align}.",
            file=sys.stderr,
        )
        buffer = buffer[:usable]
    emit_chunk(len(buffer))
    return bundle_id


def export_training_bundles_for_split(
    *,
    output_root: Path,
    training_root: Path,
    dataset_name: str,
    split_name: str,
    image_root: Union[str, Path],
    rows_per_part: int,
    row_align: int,
    on_shard_progress: Optional[Callable[[int, int, Path], None]] = None,
) -> int:
    """
    Clear previous ``data_*`` bundles under ``training_root/{dataset}/{split}``, then pack from
    ``output_root/{dataset}/{split}/metadata_qa``.
    """
    qa_dir = output_root / dataset_name / split_name / "metadata_qa"
    bundle_root = training_root / dataset_name / split_name
    bundle_root.mkdir(parents=True, exist_ok=True)
    (bundle_root / "images").mkdir(parents=True, exist_ok=True)
    (bundle_root / "jsonl").mkdir(parents=True, exist_ok=True)
    _clear_existing_training_bundles(bundle_root)
    if not qa_dir.is_dir():
        return 0
    return export_training_bundles_from_metadata_qa(
        metadata_qa_dir=qa_dir,
        bundle_root=bundle_root,
        image_root=image_root,
        rows_per_part=rows_per_part,
        row_align=row_align,
        on_shard_progress=on_shard_progress,
    )
