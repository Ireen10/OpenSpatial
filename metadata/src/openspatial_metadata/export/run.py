"""Orchestrate export: one ``MetadataV0`` with ``qa_items`` → ``images/`` + ``jsonl/``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image

from openspatial_metadata.export.grouping import group_qa_items, visual_group_key
from openspatial_metadata.export.paths import training_image_relpath
from openspatial_metadata.export.records import build_training_line
from openspatial_metadata.io.image_archive import load_pil_for_metadata
from openspatial_metadata.export.render import render_group_image_jpeg
from openspatial_metadata.export.tar_bundle import write_tar_and_tarinfo, write_tarinfo_json
from openspatial_metadata.schema.metadata_v0 import AnnotationQaItemV0, MetadataV0


def _objects_by_id(md: MetadataV0) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for o in md.objects:
        d = o.dict() if hasattr(o, "dict") else o.model_dump()
        oid = d.get("object_id")
        if isinstance(oid, str):
            out[oid] = d
    return out


def export_metadata_to_training_bundle(
    md: MetadataV0,
    *,
    image_root: Optional[Union[str, Path]] = None,
    image_tar_path: Optional[Union[str, Path]] = None,
    output_root: Union[str, Path],
    bundle_id: int = 0,
    part_id: int = 0,
) -> Dict[str, Path]:
    """
    Write ``{output_root}/images/data_{bundle_id:06d}.tar``,
    ``{output_root}/images/data_{bundle_id:06d}_tarinfo.json``,
    ``{output_root}/jsonl/data_{bundle_id:06d}.jsonl``.

    ``part_id`` is deprecated; use ``bundle_id`` (same meaning).

    Requires non-empty ``md.qa_items`` and a readable RGB image from
    ``image_root / sample.image.path`` or from member ``sample.image.path`` inside ``image_tar_path``
    (unless ``sample.image.path`` is absolute).
    """
    if part_id != 0 and bundle_id == 0:
        bundle_id = part_id
    if not md.qa_items:
        raise ValueError("metadata.qa_items is empty; populate QA before export")

    if (image_root is None) == (image_tar_path is None):
        raise ValueError("export_metadata_to_training_bundle: pass exactly one of image_root or image_tar_path")

    out = Path(output_root)
    pil = load_pil_for_metadata(md, image_root=image_root, tar_path=image_tar_path)
    width, height = pil.size
    obj_map = _objects_by_id(md)
    coord_scale = int(getattr(md.sample.image, "coord_scale", 1000) or 1000)

    groups = group_qa_items(md.qa_items)
    members: List[tuple] = []
    lines: List[Dict[str, Any]] = []

    base_rel = md.sample.image.path
    if not isinstance(base_rel, str) or not base_rel.strip():
        raise ValueError("metadata.sample.image.path must be a non-empty string")

    for group in groups:
        meta0 = dict(group[0].meta or {})
        jpeg = render_group_image_jpeg(pil, meta0, obj_map, coord_scale=float(coord_scale))
        vk = visual_group_key(meta0)
        rel = training_image_relpath(
            base_image_rel=base_rel,
            meta0=meta0,
            visual_key=vk,
        )
        members.append((rel, jpeg))
        lines.append(
            build_training_line(
                group,
                relative_path=rel,
                image_width=width,
                image_height=height,
                record_id="",
            )
        )

    from openspatial_metadata.export.stream import bundle_paths

    bp = bundle_paths(out, bundle_id)
    tar_path = bp.tar_path
    index = write_tar_and_tarinfo(tar_path, members)
    write_tarinfo_json(bp.tarinfo_path, index)

    jsonl_path = bp.jsonl_path
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {"tar": tar_path, "tarinfo": bp.tarinfo_path, "jsonl": jsonl_path}


def build_training_members_and_rows(
    md: MetadataV0,
    *,
    image_root: Optional[Union[str, Path]] = None,
    image_tar_path: Optional[Union[str, Path]] = None,
) -> Tuple[List[Tuple[str, bytes]], List[Dict[str, Any]]]:
    """
    Pure-ish helper: for one metadata record with qa_items, render group images and build training rows.
    Does NOT write files.
    """
    if not md.qa_items:
        raise ValueError("metadata.qa_items is empty; populate QA before export")
    if (image_root is None) == (image_tar_path is None):
        raise ValueError("build_training_members_and_rows: pass exactly one of image_root or image_tar_path")
    pil = load_pil_for_metadata(md, image_root=image_root, tar_path=image_tar_path)
    width, height = pil.size
    obj_map = _objects_by_id(md)
    coord_scale = int(getattr(md.sample.image, "coord_scale", 1000) or 1000)

    groups = group_qa_items(md.qa_items)
    members: List[Tuple[str, bytes]] = []
    rows: List[Dict[str, Any]] = []

    base_rel = md.sample.image.path
    if not isinstance(base_rel, str) or not base_rel.strip():
        raise ValueError("metadata.sample.image.path must be a non-empty string")

    for group in groups:
        meta0 = dict(group[0].meta or {})
        jpeg = render_group_image_jpeg(pil, meta0, obj_map, coord_scale=float(coord_scale))
        vk = visual_group_key(meta0)
        rel = training_image_relpath(base_image_rel=base_rel, meta0=meta0, visual_key=vk)
        members.append((rel, jpeg))
        rows.append(
            build_training_line(
                group,
                relative_path=rel,
                image_width=width,
                image_height=height,
                record_id="",
            )
        )
    return members, rows


def _metadata_from_payload(payload: Dict[str, Any]) -> MetadataV0:
    if hasattr(MetadataV0, "model_validate"):
        return MetadataV0.model_validate(payload)
    return MetadataV0.parse_obj(payload)


def attach_task_result_as_qa_items(md: MetadataV0, task_row: Dict[str, Any]) -> MetadataV0:
    """Build a new ``MetadataV0`` with ``qa_items`` from an ``AnnotationGenerator`` row dict."""
    n = len(task_row["question"])
    items: List[AnnotationQaItemV0] = []
    for i in range(n):
        meta = task_row["meta"][i]
        rid = meta.get("relation_id") if isinstance(meta, dict) else None
        items.append(
            AnnotationQaItemV0(
                qa_id=f"qa#{i}",
                question=task_row["question"][i],
                answer=task_row["answer"][i],
                meta=dict(meta) if isinstance(meta, dict) else {},
                relation_id=str(rid) if rid else None,
                task="spatial_relation_2d",
            )
        )
    payload = md.dict() if hasattr(md, "dict") else md.model_dump()
    payload["qa_items"] = [
        it.dict() if hasattr(it, "dict") else it.model_dump() for it in items
    ]
    return _metadata_from_payload(payload)
