"""
Pack training bundles from ``metadata_qa/data_*.jsonl`` shards.

Rows are accumulated in global order (shard index, then line order) and split into
``data_{bundle_id:06d}.{tar,jsonl}`` with ``training_rows_per_part`` rows per bundle,
with the final remainder trimmed to a multiple of ``training_row_align`` (when align > 1).
"""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

from openspatial_metadata.export.paths import disambiguate_relpath
from openspatial_metadata.export.run import build_training_members_and_rows
from openspatial_metadata.export.stream import TrainingBundlePaths, TrainingBundleWriter, bundle_paths
from openspatial_metadata.io.image_archive import resolve_image_archive_path
from openspatial_metadata.schema.metadata_v0 import MetadataV0
from openspatial_metadata.utils.pydantic_compat import model_validate_compat

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


def _delete_bundle_files(paths: TrainingBundlePaths) -> None:
    for p in (paths.tar_path, paths.tarinfo_path, paths.jsonl_path):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


def _write_remainder_sidecar(
    *,
    bundle_root: Path,
    remainder_items: List[Tuple[str, bytes, Dict[str, Any], int]],
) -> None:
    if not remainder_items:
        return
    sidecar_path = bundle_root / "jsonl" / "remainder_rows.jsonl"
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    with sidecar_path.open("a", encoding="utf-8") as f:
        for rel, data, row, input_index in remainder_items:
            payload = {
                "relative_path": rel,
                "input_index": int(input_index),
                "row": row,
                "image_b64": base64.b64encode(data).decode("ascii"),
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _iter_training_items_from_metadata_qa(
    *,
    shards: List[Path],
    image_root: Optional[Path],
    image_archive_pattern: Optional[str],
    archive_base: Optional[Path],
    on_shard_progress: Optional[Callable[[int, int, Path], None]] = None,
) -> Iterable[Tuple[str, bytes, Dict[str, Any], int]]:
    n_shards = len(shards)
    use_tar = isinstance(image_archive_pattern, str) and bool(image_archive_pattern.strip())
    for si, shard_path in enumerate(shards):
        if on_shard_progress is not None:
            on_shard_progress(si, n_shards, shard_path)
        m_shard = _SHARD_RE.match(shard_path.name)
        shard_id = int(m_shard.group(1)) if m_shard else si
        tar_path: Optional[Path] = None
        if use_tar:
            assert archive_base is not None
            tar_path = resolve_image_archive_path(image_archive_pattern.strip(), shard_id, archive_base)
            if not tar_path.is_file():
                raise FileNotFoundError(f"image archive for shard {shard_id:06d} not found: {tar_path}")
        with shard_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                md = model_validate_compat(MetadataV0, payload)
                if not md.qa_items:
                    continue
                ref = (md.aux or {}).get("record_ref") or {}
                input_index = int(ref.get("input_index", 0))
                if use_tar:
                    members, rows = build_training_members_and_rows(md, image_tar_path=tar_path)
                else:
                    assert image_root is not None
                    members, rows = build_training_members_and_rows(md, image_root=image_root)
                for (rel, data), row in zip(members, rows):
                    yield (rel, data, row, input_index)


def _export_buffered_legacy(
    *,
    shards: List[Path],
    bundle_root: Path,
    rows_per_part: int,
    row_align: int,
    image_root: Optional[Path],
    image_archive_pattern: Optional[str],
    archive_base: Optional[Path],
    training_remainder_mode: str,
    on_shard_progress: Optional[Callable[[int, int, Path], None]] = None,
) -> int:
    buffer: List[Tuple[str, bytes, Dict[str, Any], int]] = []
    bundle_id = 0

    def emit_chunk(n: int) -> None:
        nonlocal bundle_id, buffer
        if n <= 0 or len(buffer) < n:
            return
        chunk = buffer[:n]
        buffer = buffer[n:]
        _write_one_bundle(bundle_root, bundle_id, chunk)
        bundle_id += 1

    for item in _iter_training_items_from_metadata_qa(
        shards=shards,
        image_root=image_root,
        image_archive_pattern=image_archive_pattern,
        archive_base=archive_base,
        on_shard_progress=on_shard_progress,
    ):
        buffer.append(item)
        while len(buffer) >= rows_per_part:
            emit_chunk(rows_per_part)

    R = len(buffer)
    if R == 0:
        return bundle_id
    usable = (R // row_align) * row_align if row_align > 1 else R
    if usable == 0:
        if training_remainder_mode == "sidecar":
            _write_remainder_sidecar(bundle_root=bundle_root, remainder_items=buffer)
        print(
            f"[openspatial-metadata] training export: dropped {R} trailing row(s) "
            f"(not a multiple of row_align={row_align}); increase data or lower row_align.",
            file=sys.stderr,
        )
        buffer.clear()
        return bundle_id
    if usable < R:
        if training_remainder_mode == "sidecar":
            _write_remainder_sidecar(bundle_root=bundle_root, remainder_items=buffer[usable:])
        print(
            f"[openspatial-metadata] training export: dropped {R - usable} trailing row(s) "
            f"to satisfy row_align={row_align}.",
            file=sys.stderr,
        )
        buffer = buffer[:usable]
    emit_chunk(len(buffer))
    return bundle_id


def _export_streaming_writer(
    *,
    shards: List[Path],
    bundle_root: Path,
    rows_per_part: int,
    row_align: int,
    image_root: Optional[Path],
    image_archive_pattern: Optional[str],
    archive_base: Optional[Path],
    training_remainder_mode: str,
    on_shard_progress: Optional[Callable[[int, int, Path], None]] = None,
) -> int:
    bundle_id = 0
    current_paths: Optional[TrainingBundlePaths] = None
    current_writer: Optional[TrainingBundleWriter] = None
    current_items: List[Tuple[str, bytes, Dict[str, Any], int]] = []

    def _open_writer_if_needed() -> None:
        nonlocal current_paths, current_writer
        if current_writer is not None:
            return
        current_paths = bundle_paths(bundle_root, bundle_id)
        current_writer = TrainingBundleWriter(current_paths, resume=False)
        current_writer.__enter__()

    def _finalize_current_bundle() -> None:
        nonlocal bundle_id, current_paths, current_writer, current_items
        if current_writer is None:
            return
        try:
            current_writer.finalize_tarinfo()
        finally:
            current_writer.__exit__(None, None, None)
            current_writer = None
            current_paths = None
            current_items.clear()
        bundle_id += 1

    for rel, data, row, input_index in _iter_training_items_from_metadata_qa(
        shards=shards,
        image_root=image_root,
        image_archive_pattern=image_archive_pattern,
        archive_base=archive_base,
        on_shard_progress=on_shard_progress,
    ):
        _open_writer_if_needed()
        assert current_writer is not None
        rel2 = disambiguate_relpath(rel, input_index=input_index, existing=current_writer.existing_names)
        row["data"][0]["content"][0]["image"]["relative_path"] = rel2
        current_writer.add_image(rel2, data)
        current_writer.add_jsonl_row(row)
        current_items.append((rel2, data, row, input_index))
        if len(current_items) >= rows_per_part:
            _finalize_current_bundle()

    if not current_items:
        if current_writer is not None:
            current_writer.__exit__(None, None, None)
        return bundle_id

    R = len(current_items)
    usable = (R // row_align) * row_align if row_align > 1 else R
    dropped_items = current_items[usable:] if usable < R else []
    if dropped_items and training_remainder_mode == "sidecar":
        _write_remainder_sidecar(bundle_root=bundle_root, remainder_items=list(dropped_items))
    if usable == 0:
        print(
            f"[openspatial-metadata] training export: dropped {R} trailing row(s) "
            f"(not a multiple of row_align={row_align}); increase data or lower row_align.",
            file=sys.stderr,
        )
        if current_writer is not None:
            current_writer.__exit__(None, None, None)
        if current_paths is not None:
            _delete_bundle_files(current_paths)
        return bundle_id

    if usable < R:
        print(
            f"[openspatial-metadata] training export: dropped {R - usable} trailing row(s) "
            f"to satisfy row_align={row_align}.",
            file=sys.stderr,
        )
        # Rewrite the partial bundle to keep only aligned rows.
        if current_writer is not None:
            current_writer.__exit__(None, None, None)
        if current_paths is not None:
            _delete_bundle_files(current_paths)
        _write_one_bundle(bundle_root, bundle_id, current_items[:usable])
        return bundle_id + 1

    _finalize_current_bundle()
    return bundle_id


def export_training_bundles_from_metadata_qa(
    *,
    metadata_qa_dir: Path,
    bundle_root: Path,
    rows_per_part: int,
    row_align: int,
    image_root: Optional[Union[str, Path]] = None,
    image_archive_pattern: Optional[str] = None,
    image_archive_base_dir: Optional[Union[str, Path]] = None,
    pipeline_streaming_enabled: bool = True,
    training_remainder_mode: str = "drop",
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

    use_tar = isinstance(image_archive_pattern, str) and image_archive_pattern.strip()
    mode = str(training_remainder_mode or "drop").strip().lower()
    if mode not in ("drop", "sidecar"):
        raise ValueError(f"training_remainder_mode must be 'drop' or 'sidecar', got: {training_remainder_mode!r}")
    image_root_p: Optional[Path] = None
    archive_base: Optional[Path] = None
    if use_tar:
        if not image_archive_base_dir:
            raise ValueError("image_archive_base_dir is required when image_archive_pattern is set")
        archive_base = Path(image_archive_base_dir).resolve()
    else:
        if image_root is None:
            raise ValueError("image_root is required when image_archive_pattern is not set")
        image_root_p = Path(image_root)

    shards = _sorted_metadata_qa_shards(metadata_qa_dir)
    if not shards:
        return 0
    if pipeline_streaming_enabled:
        return _export_streaming_writer(
            shards=shards,
            bundle_root=bundle_root,
            rows_per_part=rows_per_part,
            row_align=row_align,
            image_root=image_root_p,
            image_archive_pattern=image_archive_pattern,
            archive_base=archive_base,
            training_remainder_mode=mode,
            on_shard_progress=on_shard_progress,
        )
    return _export_buffered_legacy(
        shards=shards,
        bundle_root=bundle_root,
        rows_per_part=rows_per_part,
        row_align=row_align,
        image_root=image_root_p,
        image_archive_pattern=image_archive_pattern,
        archive_base=archive_base,
        training_remainder_mode=mode,
        on_shard_progress=on_shard_progress,
    )


def export_training_bundles_for_split(
    *,
    output_root: Path,
    training_root: Path,
    dataset_name: str,
    split_name: str,
    image_root: Optional[Union[str, Path]] = None,
    image_archive_pattern: Optional[str] = None,
    image_archive_base_dir: Optional[Union[str, Path]] = None,
    rows_per_part: int,
    row_align: int,
    pipeline_streaming_enabled: bool = True,
    training_remainder_mode: str = "drop",
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
        rows_per_part=rows_per_part,
        row_align=row_align,
        pipeline_streaming_enabled=pipeline_streaming_enabled,
        training_remainder_mode=training_remainder_mode,
        image_root=image_root,
        image_archive_pattern=image_archive_pattern,
        image_archive_base_dir=image_archive_base_dir,
        on_shard_progress=on_shard_progress,
    )
