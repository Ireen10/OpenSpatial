from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


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
    for key in ("objects", "instances", "annotations"):
        vv = record.get(key)
        if isinstance(vv, list):
            for it in vv:
                if isinstance(it, dict):
                    yield it
            return


class Omni3DAdapter:
    """
    Normalize Omni3D-like samples into MetadataV0-compatible dict.
    """

    def __init__(
        self,
        *,
        dataset_name: str = "omni3d",
        split: str = "unknown",
        coord_space: str = "norm_0_999",
        coord_scale: int = 1000,
    ):
        self.dataset_name = dataset_name
        self.split = split
        self.coord_space = coord_space
        self.coord_scale = coord_scale

    def convert(self, record: Dict[str, Any]) -> Dict[str, Any]:
        sample_id = _pick_str(record, ("sample_id", "id", "image_id"), "unknown")
        image_path = _pick_str(record, ("image_path", "img_path", "file_name"), "")
        width = record.get("width")
        height = record.get("height")

        objects: List[Dict[str, Any]] = []
        for i, obj in enumerate(_iter_objects(record)):
            oid = _pick_str(obj, ("object_id", "id", "annotation_id"), f"obj#{i}")
            out = {
                "object_id": oid,
                "category": _pick_str(obj, ("category", "category_name", "label"), ""),
                "phrase": _pick_str(obj, ("phrase", "description", "text"), "") or None,
            }
            bb = obj.get("bbox_xyxy_norm_1000")
            if isinstance(bb, (list, tuple)) and len(bb) == 4:
                out["bbox_xyxy_norm_1000"] = [int(x) for x in bb]
            center = None
            for key in ("center_xyz_cam", "center_3d", "center_cam", "xyz_cam"):
                center = _to_float3(obj.get(key))
                if center is not None:
                    break
            if center is not None:
                out["center_xyz_cam"] = center
            objects.append(out)

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
            "relations": [],
            "qa_items": [],
            "aux": {"adapter_name": "Omni3DAdapter"},
        }

