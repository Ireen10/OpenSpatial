"""
2D image_plane relation enrichment on :class:`MetadataV0`.

Convention: ``delta_uv = target - anchor`` (representative points). Predicate describes
**target relative to anchor** (e.g. ``right`` ⇒ target is to the right of anchor, ``du > 0``).
``above`` ⇒ smaller ``v`` (image y increases downward).
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from ..schema.metadata_v0 import MetadataV0, ObjectV0, RelationV0
from . import constants as C
from .filters import ObjectFilterOptions, filter_objects


def _effective_scale(md: MetadataV0) -> int:
    s = md.sample.image.coord_scale
    return int(s) if s is not None else C.REF_COORD_SCALE


def rep_point_uv(obj: ObjectV0) -> Tuple[float, float]:
    bb = obj.bbox_xyxy_norm_1000
    pt = obj.point_uv_norm_1000
    if bb is not None and pt is not None:
        raise ValueError(f"object {obj.object_id} has both bbox and point")
    if bb is not None:
        x1, y1, x2, y2 = bb
        return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)
    if pt is not None:
        return (float(pt[0]), float(pt[1]))
    raise ValueError(f"object {obj.object_id} has no geometry")


def bbox_iou(a: List[int], b: List[int]) -> float:
    xa1, ya1, xa2, ya2 = a
    xb1, yb1, xb2, yb2 = b
    ix1, iy1 = max(xa1, xb1), max(ya1, yb1)
    ix2, iy2 = min(xa2, xb2), min(ya2, yb2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    aa = max(0, xa2 - xa1) * max(0, ya2 - ya1)
    bb_ = max(0, xb2 - xb1) * max(0, yb2 - yb1)
    union = aa + bb_ - inter
    if union <= 0:
        return 0.0
    return inter / union


def _euclid(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _strip_old_computed_image_plane(relations: List[RelationV0]) -> List[RelationV0]:
    out: List[RelationV0] = []
    for r in relations:
        if r.ref_frame == "image_plane" and (r.source or "") == "computed":
            continue
        out.append(r)
    return out


def _existing_image_plane_triples(relations: List[RelationV0]) -> set[tuple[str, str, str]]:
    """Directed (anchor_id, target_id, ref_frame) for existing image_plane edges."""
    return {(r.anchor_id, r.target_id, r.ref_frame) for r in relations if r.ref_frame == "image_plane"}


def _build_relation(
    anchor_id: str,
    target_id: str,
    du: float,
    dv: float,
    anc_pt: Tuple[float, float],
    tgt_pt: Tuple[float, float],
    method_anchor: str,
    method_target: str,
    *,
    predicate: str,
    components: Optional[List[str]],
    axis_signs: Optional[Dict[str, int]],
) -> RelationV0:
    ev: Dict[str, Any] = {
        "method": f"{method_anchor}+{method_target}",
        "anchor_point_uv_norm_1000": [int(round(anc_pt[0])), int(round(anc_pt[1]))],
        "target_point_uv_norm_1000": [int(round(tgt_pt[0])), int(round(tgt_pt[1]))],
        "delta_uv": [int(round(du)), int(round(dv))],
    }
    return RelationV0(
        anchor_id=anchor_id,
        target_id=target_id,
        predicate=predicate,
        ref_frame="image_plane",
        components=components,
        axis_signs=axis_signs,
        source="computed",
        evidence=ev,
    )


def _geom_method(obj: ObjectV0) -> str:
    return "bbox_center" if obj.bbox_xyxy_norm_1000 is not None else "point_uv"


def _maybe_relation_for_pair(
    anchor: ObjectV0,
    target: ObjectV0,
    *,
    min_du: float,
    min_dv: float,
    near_center: float,
    iou_th: float,
    dropped_candidates: List[Dict[str, Any]],
) -> Optional[RelationV0]:
    ab, bb = anchor.bbox_xyxy_norm_1000, target.bbox_xyxy_norm_1000
    if ab is not None and bb is not None:
        iou = bbox_iou(ab, bb)
        if iou > iou_th:
            dropped_candidates.append(
                {"anchor_id": anchor.object_id, "target_id": target.object_id, "reason": "high_iou"}
            )
            return None

    pa = rep_point_uv(anchor)
    pb = rep_point_uv(target)
    dist = _euclid(pa, pb)
    if dist < near_center:
        dropped_candidates.append(
            {"anchor_id": anchor.object_id, "target_id": target.object_id, "reason": "near_center"}
        )
        return None

    du, dv = pb[0] - pa[0], pb[1] - pa[1]
    adu, adv = abs(du), abs(dv)

    if adu < min_du and adv < min_dv:
        return None

    h_ok = adu >= min_du
    v_ok = adv >= min_dv

    ma, mb = _geom_method(anchor), _geom_method(target)

    if h_ok and v_ok:
        h_atom = "right" if du > 0 else "left"
        v_atom = "above" if dv < 0 else "below"
        components = [h_atom, v_atom]
        # Composite: semantic truth is `components`; `predicate` matches horizontal
        # leg only so RelationV0.predicate stays a single atomic label without a
        # bogus "main axis" from |du| vs |dv|.
        predicate = components[0]
        axis = {"right": 1 if du > 0 else (-1 if du < 0 else 0), "above": 1 if dv < 0 else (-1 if dv > 0 else 0)}
        return _build_relation(
            anchor.object_id,
            target.object_id,
            du,
            dv,
            pa,
            pb,
            ma,
            mb,
            predicate=predicate,
            components=components,
            axis_signs=axis,
        )

    if h_ok and not v_ok:
        if du == 0:
            return None
        pred = "right" if du > 0 else "left"
        return _build_relation(
            anchor.object_id,
            target.object_id,
            du,
            dv,
            pa,
            pb,
            ma,
            mb,
            predicate=pred,
            components=None,
            axis_signs=None,
        )

    if v_ok and not h_ok:
        if dv == 0:
            return None
        pred = "above" if dv < 0 else "below"
        return _build_relation(
            anchor.object_id,
            target.object_id,
            du,
            dv,
            pa,
            pb,
            ma,
            mb,
            predicate=pred,
            components=None,
            axis_signs=None,
        )

    return None


def enrich_relations_2d(
    metadata: MetadataV0,
    *,
    object_filter_options: Optional[ObjectFilterOptions] = None,
) -> MetadataV0:
    """
    Return a deep copy of *metadata* with ``relations`` extended by computed
    ``image_plane`` edges; existing ``source=='computed'`` + same ref_frame rows are removed first.

    If a relation already exists with the same **(anchor_id, target_id, ref_frame)** and
    ``ref_frame == "image_plane"`` among the kept (non-stripped) rows, that ordered pair is
    **not** recomputed (avoids duplicate edges next to imported / manual rows).

    Raises:
        ValueError: if any object carries both bbox and point.
    """
    md = deepcopy(metadata)
    scale = _effective_scale(md)
    dropped_objects: List[Dict[str, Any]] = []
    dropped_candidates: List[Dict[str, Any]] = []

    for o in md.objects:
        if o.bbox_xyxy_norm_1000 is not None and o.point_uv_norm_1000 is not None:
            raise ValueError(f"object {o.object_id} has both bbox_xyxy_norm_1000 and point_uv_norm_1000")

    opts = object_filter_options or ObjectFilterOptions()
    n_in = len(md.objects)
    kept = filter_objects(md.objects, scale, opts, dropped_objects)
    n_kept = len(kept)

    min_du = C.scale_length(float(C.MIN_ABS_DELTA_U_REF), scale)
    min_dv = C.scale_length(float(C.MIN_ABS_DELTA_V_REF), scale)
    near_d = C.scale_length(float(C.NEAR_CENTER_DIST_REF), scale)

    base_relations = _strip_old_computed_image_plane(md.relations)
    skip_triples = _existing_image_plane_triples(base_relations)

    sorted_objs = sorted(kept, key=lambda o: o.object_id)
    new_rels: List[RelationV0] = []
    pairs = 0
    skipped_existing = 0
    for i in range(len(sorted_objs)):
        for j in range(i + 1, len(sorted_objs)):
            a, b = sorted_objs[i], sorted_objs[j]
            anchor, target = (a, b) if a.object_id < b.object_id else (b, a)
            pairs += 1
            triple = (anchor.object_id, target.object_id, "image_plane")
            if triple in skip_triples:
                skipped_existing += 1
                continue
            rel = _maybe_relation_for_pair(
                anchor,
                target,
                min_du=min_du,
                min_dv=min_dv,
                near_center=near_d,
                iou_th=C.AMBIGUOUS_IOU,
                dropped_candidates=dropped_candidates,
            )
            if rel is not None:
                new_rels.append(rel)

    md.relations = base_relations + new_rels
    md.aux.setdefault("enrich_2d", {})
    md.aux["enrich_2d"].update(
        {
            "dropped_objects": dropped_objects,
            "dropped_relation_candidates": dropped_candidates,
            "stats": {
                "n_objects_in": n_in,
                "n_objects_kept": n_kept,
                "n_pairs_considered": pairs,
                "n_pairs_skipped_existing": skipped_existing,
                "n_relations_out": len(new_rels),
            },
        }
    )
    return md
