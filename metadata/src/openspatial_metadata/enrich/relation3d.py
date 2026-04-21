"""
3D egocentric relation enrichment on :class:`MetadataV0`.

Convention:
- relation describes **target relative to anchor**.
- camera axis is assumed x-right, y-down, z-forward.
- `front` means target is closer to camera than anchor (smaller z), so front sign is `-dz`.
- `above` means target is higher than anchor (smaller y), so up sign is `-dy`.
"""

from __future__ import annotations

from copy import deepcopy
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from ..schema.metadata_v0 import MetadataV0, RelationV0
from ..utils.pydantic_compat import model_dump_compat

_AXIS_ORDER = ("front", "right", "above")


def _to_float3(v: Any) -> Optional[Tuple[float, float, float]]:
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        return None
    out: List[float] = []
    for x in v:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            return None
    return (out[0], out[1], out[2])


def _rep_point_xyz(obj: Dict[str, Any]) -> Optional[Tuple[float, float, float]]:
    # Preferred canonical field used by this project.
    c = _to_float3(obj.get("center_xyz_cam"))
    if c is not None:
        return c
    # Common alternatives from upstream datasets.
    for key in ("point_xyz_cam", "center_3d", "centroid_xyz_cam", "centroid"):
        c = _to_float3(obj.get(key))
        if c is not None:
            return c
    # Fallback for OBB-like payloads: [cx,cy,cz,...].
    obb = obj.get("obb_world")
    if isinstance(obb, (list, tuple)) and len(obb) >= 3:
        c = _to_float3(list(obb[:3]))
        if c is not None:
            return c
    return None


def _strip_old_computed_egocentric(relations: List[RelationV0]) -> List[RelationV0]:
    out: List[RelationV0] = []
    for r in relations:
        src = str(r.source or "")
        if r.ref_frame == "egocentric" and src.startswith("computed"):
            continue
        out.append(r)
    return out


def _existing_egocentric_triples(relations: List[RelationV0]) -> set[tuple[str, str, str]]:
    return {(r.anchor_id, r.target_id, r.ref_frame) for r in relations if r.ref_frame == "egocentric"}


def _sign(v: float, *, th: float) -> int:
    if v > th:
        return 1
    if v < -th:
        return -1
    return 0


def _components_from_signs(axis_signs: Dict[str, int]) -> List[str]:
    out: List[str] = []
    if axis_signs.get("front", 0) > 0:
        out.append("front")
    elif axis_signs.get("front", 0) < 0:
        out.append("behind")

    if axis_signs.get("right", 0) > 0:
        out.append("right")
    elif axis_signs.get("right", 0) < 0:
        out.append("left")

    if axis_signs.get("above", 0) > 0:
        out.append("above")
    elif axis_signs.get("above", 0) < 0:
        out.append("below")
    return out


def _predicate_from_components(components: List[str]) -> str:
    if not components:
        return "front"
    # Keep a deterministic dominant axis priority.
    order = {name: i for i, name in enumerate(_AXIS_ORDER)}
    return sorted(components, key=lambda x: order.get(x, 99))[0]


def _components_from_relation_payload(rel: Dict[str, Any]) -> List[str]:
    comps = rel.get("components")
    if isinstance(comps, list):
        out = [str(x).strip().lower() for x in comps if str(x).strip()]
        if out:
            return out
    pred = str(rel.get("predicate") or "").strip().lower()
    if pred:
        return [pred]
    axis = rel.get("axis_signs")
    if isinstance(axis, dict):
        return _components_from_signs(
            {
                "front": int(axis.get("front", 0) or 0),
                "right": int(axis.get("right", 0) or 0),
                "above": int(axis.get("above", 0) or 0),
            }
        )
    return []


def _build_relation(
    *,
    anchor_id: str,
    target_id: str,
    anchor_xyz: Tuple[float, float, float],
    target_xyz: Tuple[float, float, float],
    axis_signs: Dict[str, int],
) -> RelationV0:
    dx = target_xyz[0] - anchor_xyz[0]
    dy = target_xyz[1] - anchor_xyz[1]
    dz = target_xyz[2] - anchor_xyz[2]
    components = _components_from_signs(axis_signs)
    predicate = _predicate_from_components(components)
    return RelationV0(
        anchor_id=anchor_id,
        target_id=target_id,
        predicate=predicate,
        ref_frame="egocentric",
        components=components if components else None,
        axis_signs=axis_signs,
        source="computed_3d",
        evidence={
            "method": "center_xyz_cam",
            "anchor_point_xyz_cam": [anchor_xyz[0], anchor_xyz[1], anchor_xyz[2]],
            "target_point_xyz_cam": [target_xyz[0], target_xyz[1], target_xyz[2]],
            "delta_xyz_cam": [dx, dy, dz],
            "front_order": "target_closer" if dz < 0 else ("anchor_closer" if dz > 0 else "tie"),
        },
    )


def enrich_relations_3d(
    metadata: MetadataV0,
    *,
    min_abs_delta_x: float = 0.05,
    min_abs_delta_y: float = 0.05,
    min_abs_delta_z: float = 0.05,
) -> MetadataV0:
    """
    Return a deep copy with computed egocentric 3D relations appended.

    Notes:
    - Existing non-computed egocentric relations are preserved.
    - Existing same-direction triples (anchor, target, egocentric) are not recomputed.
    """
    md = deepcopy(metadata)
    dropped_candidates: List[Dict[str, Any]] = []

    base_relations = _strip_old_computed_egocentric(md.relations)
    skip_triples = _existing_egocentric_triples(base_relations)

    obj_rows = [model_dump_compat(o) for o in md.objects]
    obj_rows = [o for o in obj_rows if isinstance(o.get("object_id"), str) and o.get("object_id")]
    obj_rows.sort(key=lambda x: str(x["object_id"]))

    computed: List[RelationV0] = []
    pairs = 0
    skipped_existing = 0
    conflict_examples: List[Dict[str, Any]] = []
    pairs_with_geometry = 0
    existing_by_triple: Dict[Tuple[str, str, str], List[RelationV0]] = {}
    for rel in base_relations:
        if rel.ref_frame != "egocentric":
            continue
        tri = (str(rel.anchor_id), str(rel.target_id), "egocentric")
        existing_by_triple.setdefault(tri, []).append(rel)
    for i in range(len(obj_rows)):
        for j in range(i + 1, len(obj_rows)):
            a = obj_rows[i]
            b = obj_rows[j]
            anchor, target = (a, b) if str(a["object_id"]) < str(b["object_id"]) else (b, a)
            pairs += 1
            triple = (str(anchor["object_id"]), str(target["object_id"]), "egocentric")
            if triple in skip_triples:
                skipped_existing += 1
            pa = _rep_point_xyz(anchor)
            pb = _rep_point_xyz(target)
            if pa is None or pb is None:
                if triple not in skip_triples:
                    dropped_candidates.append(
                        {
                            "anchor_id": str(anchor["object_id"]),
                            "target_id": str(target["object_id"]),
                            "reason": "missing_3d_geometry",
                        }
                    )
                continue
            pairs_with_geometry += 1

            if triple in skip_triples:
                existing = existing_by_triple.get(triple, [])
                for rel0 in existing:
                    src = str(rel0.source or "")
                    if not src.startswith("annotated"):
                        continue
                    rel_payload = model_dump_compat(rel0)
                    annotated_components = _components_from_relation_payload(rel_payload)
                    dx = pb[0] - pa[0]
                    dy = pb[1] - pa[1]
                    dz = pb[2] - pa[2]
                    inferred_axis = {
                        "right": _sign(dx, th=float(min_abs_delta_x)),
                        "above": _sign(-dy, th=float(min_abs_delta_y)),
                        "front": _sign(-dz, th=float(min_abs_delta_z)),
                    }
                    inferred_components = _components_from_signs(inferred_axis)
                    if set(annotated_components) != set(inferred_components):
                        if len(conflict_examples) < 20:
                            conflict_examples.append(
                                {
                                    "anchor_id": str(anchor["object_id"]),
                                    "target_id": str(target["object_id"]),
                                    "annotated_components": annotated_components,
                                    "inferred_components": inferred_components,
                                    "delta_xyz_cam": [dx, dy, dz],
                                }
                            )
                continue

            dx = pb[0] - pa[0]
            dy = pb[1] - pa[1]
            dz = pb[2] - pa[2]

            axis = {
                "right": _sign(dx, th=float(min_abs_delta_x)),
                "above": _sign(-dy, th=float(min_abs_delta_y)),
                "front": _sign(-dz, th=float(min_abs_delta_z)),
            }
            if axis["right"] == 0 and axis["above"] == 0 and axis["front"] == 0:
                dropped_candidates.append(
                    {
                        "anchor_id": str(anchor["object_id"]),
                        "target_id": str(target["object_id"]),
                        "reason": "tiny_delta_3d",
                        "delta_xyz_cam": [dx, dy, dz],
                    }
                )
                continue
            computed.append(
                _build_relation(
                    anchor_id=str(anchor["object_id"]),
                    target_id=str(target["object_id"]),
                    anchor_xyz=pa,
                    target_xyz=pb,
                    axis_signs=axis,
                )
            )

    md.relations = MetadataV0.ensure_relation_ids(base_relations + computed)
    source_counts: Dict[str, int] = dict(Counter(str(r.source or "unknown") for r in md.relations))
    md.aux.setdefault("enrich_3d", {})
    md.aux["enrich_3d"].update(
        {
            "dropped_relation_candidates": dropped_candidates,
            "conflicts_annotated_vs_geometry": conflict_examples,
            "stats": {
                "n_objects_in": len(md.objects),
                "n_pairs_considered": pairs,
                "n_pairs_with_geometry": pairs_with_geometry,
                "n_pairs_skipped_existing": skipped_existing,
                "n_relations_out_computed": len(computed),
                "n_relations_out_total": len(md.relations),
                "relation_sources": source_counts,
                "n_conflicts_annotated_vs_geometry": len(conflict_examples),
            },
        }
    )
    return md

