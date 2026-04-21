from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..schema.metadata_v0 import MetadataV0


def _pick_str(d: Dict[str, Any], keys: Iterable[str], default: str = "") -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def _to_float3(v: Any) -> Optional[List[float]]:
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        return None
    out: List[float] = []
    for x in v:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            return None
    return out


def _iter_objects(record: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for k in ("objects", "instances", "annotations"):
        vv = record.get(k)
        if isinstance(vv, list):
            for it in vv:
                if isinstance(it, dict):
                    yield it
            return


def _iter_relations(record: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for k in ("relations_3d", "relations3d", "spatial_relations_3d"):
        vv = record.get(k)
        if isinstance(vv, list):
            for it in vv:
                if isinstance(it, dict):
                    yield it
            return


class EmbodiedScan3DAdapter:
    """
    Normalize EmbodiedScan-like records to MetadataV0-compatible dict.
    """

    def __init__(
        self,
        *,
        dataset_name: str = "embodiedscan",
        split: str = "unknown",
        coord_space: str = "norm_0_999",
        coord_scale: int = 1000,
    ):
        self.dataset_name = dataset_name
        self.split = split
        self.coord_space = coord_space
        self.coord_scale = coord_scale

    def convert(self, record: Dict[str, Any]) -> Dict[str, Any]:
        sample_id = _pick_str(record, ("sample_id", "id", "scene_id"), "unknown")
        image_path = _pick_str(record, ("image_path", "img_path", "image", "image_file"), "")
        width = record.get("width")
        height = record.get("height")

        objects: List[Dict[str, Any]] = []
        oid_map: Dict[str, str] = {}
        idx = 0
        for obj in _iter_objects(record):
            raw_oid = _pick_str(obj, ("object_id", "id", "instance_id"), f"obj#{idx}")
            oid = raw_oid if raw_oid else f"obj#{idx}"
            idx += 1
            oid_map[raw_oid] = oid
            center = None
            for key in ("center_xyz_cam", "center_3d", "centroid", "centroid_xyz_cam"):
                center = _to_float3(obj.get(key))
                if center is not None:
                    break
            out = {
                "object_id": oid,
                "category": _pick_str(obj, ("category", "label", "category_name"), ""),
                "phrase": _pick_str(obj, ("phrase", "text", "description"), "") or None,
            }
            if center is not None:
                out["center_xyz_cam"] = center
            bbox = obj.get("bbox_xyxy_norm_1000")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                out["bbox_xyxy_norm_1000"] = [int(x) for x in bbox]
            objects.append(out)

        relations: List[Dict[str, Any]] = []
        for rel in _iter_relations(record):
            a0 = _pick_str(rel, ("anchor_id", "subject_id", "src"), "")
            t0 = _pick_str(rel, ("target_id", "object_id", "dst"), "")
            a = oid_map.get(a0, a0)
            t = oid_map.get(t0, t0)
            if not a or not t:
                continue
            row: Dict[str, Any] = {
                "anchor_id": a,
                "target_id": t,
                "predicate": _pick_str(rel, ("predicate", "relation"), "front"),
                "ref_frame": "egocentric",
                "source": _pick_str(rel, ("source",), "annotated_3d"),
            }
            comps = rel.get("components")
            if isinstance(comps, list):
                row["components"] = [str(x) for x in comps if str(x)]
            axis = rel.get("axis_signs")
            if isinstance(axis, dict):
                row["axis_signs"] = {k: int(v) for k, v in axis.items() if k in ("right", "above", "front")}
            if isinstance(rel.get("evidence"), dict):
                row["evidence"] = dict(rel["evidence"])
            relations.append(row)

        return {
            "dataset": {"name": self.dataset_name, "version": "v0", "split": self.split},
            "sample": {
                "sample_id": sample_id,
                "view_id": 0,
                "image": {
                    "path": image_path,
                    "width": int(width) if isinstance(width, int) else None,
                    "height": int(height) if isinstance(height, int) else None,
                    "coord_space": self.coord_space,
                    "coord_scale": self.coord_scale,
                },
            },
            "camera": record.get("camera"),
            "objects": objects,
            "queries": [],
            "relations": relations,
            "qa_items": [],
            "aux": {"adapter_name": "EmbodiedScan3DAdapter"},
        }

