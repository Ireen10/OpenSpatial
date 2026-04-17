"""Orchestrate export: one ``MetadataV0`` with ``qa_items`` → ``images/`` + ``jsonl/``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Union

from PIL import Image

from openspatial_metadata.export.grouping import group_qa_items, visual_group_key
from openspatial_metadata.export.paths import training_image_relpath
from openspatial_metadata.export.records import build_training_line
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


def _resolve_image_path(md: MetadataV0, image_root: Union[str, Path]) -> Path:
    rel = md.sample.image.path
    p = Path(rel)
    if p.is_absolute():
        return p
    return Path(image_root) / rel


def export_metadata_to_training_bundle(
    md: MetadataV0,
    *,
    image_root: Union[str, Path],
    output_root: Union[str, Path],
    part_id: int = 0,
) -> Dict[str, Path]:
    """
    Write ``{output_root}/images/part_{part_id:06d}.tar``,
    ``{output_root}/images/part_{part_id:06d}_tarinfo.json``,
    ``{output_root}/jsonl/part_{part_id:06d}.jsonl``.

    Requires non-empty ``md.qa_items`` and a readable RGB image at
    ``image_root / sample.image.path`` (unless path is absolute).
    """
    if not md.qa_items:
        raise ValueError("metadata.qa_items is empty; populate QA before export")

    out = Path(output_root)
    img_path = _resolve_image_path(md, image_root)
    if not img_path.is_file():
        raise FileNotFoundError(f"image not found: {img_path}")

    with Image.open(img_path) as im_f:
        pil = im_f.convert("RGB").copy()
    width, height = pil.size
    obj_map = _objects_by_id(md)

    groups = group_qa_items(md.qa_items)
    members: List[tuple] = []
    lines: List[Dict[str, Any]] = []

    base_rel = md.sample.image.path
    if not isinstance(base_rel, str) or not base_rel.strip():
        raise ValueError("metadata.sample.image.path must be a non-empty string")

    for group in groups:
        meta0 = dict(group[0].meta or {})
        jpeg = render_group_image_jpeg(pil, meta0, obj_map)
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

    images_dir = out / "images"
    jsonl_dir = out / "jsonl"
    images_dir.mkdir(parents=True, exist_ok=True)
    jsonl_dir.mkdir(parents=True, exist_ok=True)

    tar_path = images_dir / f"part_{part_id:06d}.tar"
    index = write_tar_and_tarinfo(tar_path, members)
    write_tarinfo_json(images_dir / f"part_{part_id:06d}_tarinfo.json", index)

    jsonl_path = jsonl_dir / f"part_{part_id:06d}.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {"tar": tar_path, "tarinfo": images_dir / f"part_{part_id:06d}_tarinfo.json", "jsonl": jsonl_path}


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
