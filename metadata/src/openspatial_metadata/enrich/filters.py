from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ..schema.metadata_v0 import ObjectV0
from . import constants as C


@dataclass
class ObjectFilterOptions:
    min_area_abs: float | None = None  # default from constants at runtime scale
    min_area_frac: float = 0.0
    max_aspect_ratio: float = C.MAX_ASPECT_RATIO
    max_objects_per_sample: int | None = None
    reject_out_of_bounds: bool = True


def _bbox_area_xyxy(b: List[int]) -> float:
    x1, y1, x2, y2 = b
    return float(max(0, x2 - x1) * max(0, y2 - y1))


def _aspect_ratio(b: List[int]) -> float:
    x1, y1, x2, y2 = b
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)
    return max(w / h, h / w)


def _in_bounds_bbox(b: List[int], scale: int) -> bool:
    x1, y1, x2, y2 = b
    if min(x1, y1, x2, y2) < 0:
        return False
    if max(x1, x2) >= scale or max(y1, y2) >= scale:
        return False
    return True


def _in_bounds_point(p: List[int], scale: int) -> bool:
    u, v = p
    return 0 <= u < scale and 0 <= v < scale


def filter_objects(
    objects: List[ObjectV0],
    scale: int,
    opts: ObjectFilterOptions,
    dropped: List[Dict[str, Any]],
) -> List[ObjectV0]:
    min_area_abs = opts.min_area_abs if opts.min_area_abs is not None else C.scale_area(float(C.MIN_AREA_ABS_REF), scale)

    kept: List[ObjectV0] = []
    for obj in objects:
        bid = obj.object_id
        bb = obj.bbox_xyxy_norm_1000
        pt = obj.point_uv_norm_1000
        if bb is not None and pt is not None:
            raise ValueError(f"object {bid} has both bbox_xyxy_norm_1000 and point_uv_norm_1000")
        if bb is not None:
            x1, y1, x2, y2 = bb
            if x2 <= x1 or y2 <= y1 or math.isnan(x1 + x2 + y1 + y2):
                dropped.append({"object_id": bid, "reason": "geom_invalid"})
                continue
            area = _bbox_area_xyxy(bb)
            if area <= 0:
                dropped.append({"object_id": bid, "reason": "geom_invalid"})
                continue
            if opts.reject_out_of_bounds and not _in_bounds_bbox(bb, scale):
                dropped.append({"object_id": bid, "reason": "out_of_bounds"})
                continue
            if area < min_area_abs:
                dropped.append({"object_id": bid, "reason": "min_area"})
                continue
            if _aspect_ratio(bb) > opts.max_aspect_ratio:
                dropped.append({"object_id": bid, "reason": "aspect_ratio"})
                continue
            kept.append(obj)
        elif pt is not None:
            if len(pt) != 2 or any(math.isnan(float(t)) for t in pt):
                dropped.append({"object_id": bid, "reason": "geom_invalid"})
                continue
            if opts.reject_out_of_bounds and not _in_bounds_point(pt, scale):
                dropped.append({"object_id": bid, "reason": "out_of_bounds"})
                continue
            kept.append(obj)
        else:
            dropped.append({"object_id": bid, "reason": "no_geometry"})

    if opts.min_area_frac > 0:
        # largest bbox area as proxy for image extent
        max_a = max((_bbox_area_xyxy(o.bbox_xyxy_norm_1000) for o in kept if o.bbox_xyxy_norm_1000), default=0.0)
        if max_a > 0:
            frac_kept: List[ObjectV0] = []
            for o in kept:
                bb = o.bbox_xyxy_norm_1000
                if bb is None:
                    frac_kept.append(o)
                    continue
                if _bbox_area_xyxy(bb) / max_a >= opts.min_area_frac:
                    frac_kept.append(o)
                else:
                    dropped.append({"object_id": o.object_id, "reason": "min_area_frac"})
            kept = frac_kept

    if opts.max_objects_per_sample is not None and len(kept) > opts.max_objects_per_sample:

        def sort_key(o: ObjectV0) -> Tuple[float, str]:
            if o.bbox_xyxy_norm_1000 is not None:
                return (-_bbox_area_xyxy(o.bbox_xyxy_norm_1000), o.object_id)
            return (0.0, o.object_id)

        kept_sorted = sorted(kept, key=sort_key)
        survivors = kept_sorted[: opts.max_objects_per_sample]
        cut = set(o.object_id for o in kept_sorted[opts.max_objects_per_sample :])
        for oid in cut:
            dropped.append({"object_id": oid, "reason": "cap_exceeded"})
        kept = survivors

    return kept
