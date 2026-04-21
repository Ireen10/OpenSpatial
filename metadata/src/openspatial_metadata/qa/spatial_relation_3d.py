from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..schema.metadata_v0 import AnnotationQaItemV0, MetadataV0
from ..utils.pydantic_compat import model_dump_compat
from .runtime_stats import record_spatial_relation_3d_qa_stats

ATOMIC = "atomic"
COMPOSITE = "composite"
JUDGMENT = "judgment"
STYLE_ORDER = (ATOMIC, COMPOSITE, JUDGMENT)


def _default_sub_tasks() -> Dict[str, int]:
    return {ATOMIC: 2, COMPOSITE: 2, JUDGMENT: 2}


@dataclass(frozen=True)
class SpatialRelation3DConfig:
    random_seed: Optional[int] = 11
    judgment_true_prob: float = 0.5
    sub_tasks: Dict[str, int] = field(default_factory=_default_sub_tasks)


def _direction_components(rel: Dict[str, Any]) -> List[str]:
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
        out: List[str] = []
        rv = int(axis.get("right", 0) or 0)
        uv = int(axis.get("above", 0) or 0)
        fv = int(axis.get("front", 0) or 0)
        if rv > 0:
            out.append("right")
        elif rv < 0:
            out.append("left")
        if uv > 0:
            out.append("above")
        elif uv < 0:
            out.append("below")
        if fv > 0:
            out.append("front")
        elif fv < 0:
            out.append("behind")
        return out
    return []


def _display_name(obj: Dict[str, Any]) -> str:
    phrase = str(obj.get("phrase") or "").strip()
    if phrase:
        return phrase
    return str(obj.get("category") or obj.get("object_id") or "object").strip() or "object"


def _build_atomic_qa(anchor: str, target: str, gt: str) -> tuple[str, str]:
    q = f"In 3D egocentric space, where is {target} relative to {anchor}?"
    return q, gt


def _build_composite_qa(anchor: str, target: str, gt_composite: str) -> tuple[str, str]:
    q = f"Describe the 3D egocentric relation of {target} relative to {anchor} using directional words."
    return q, gt_composite


def _build_judgment_qa(rng: random.Random, anchor: str, target: str, gt_comp: List[str], true_prob: float) -> tuple[str, str, str]:
    true_mode = rng.random() < float(true_prob)
    if true_mode:
        statement = " and ".join(gt_comp)
        q = f"Judgment: Is this statement true? In 3D egocentric space, {target} is {statement} of {anchor}."
        return q, "true", statement
    # simple negative: flip first available axis word
    flips = {
        "left": "right",
        "right": "left",
        "above": "below",
        "below": "above",
        "front": "behind",
        "behind": "front",
    }
    bad = list(gt_comp)
    if bad:
        bad[0] = flips.get(bad[0], bad[0])
    statement = " and ".join(bad or ["front"])
    q = f"Judgment: Is this statement true? In 3D egocentric space, {target} is {statement} of {anchor}."
    return q, "false", statement


def _iter_candidates(md: MetadataV0) -> List[Dict[str, Any]]:
    objects = [model_dump_compat(o) for o in (md.objects or [])]
    obj_map = {str(o.get("object_id")): o for o in objects if isinstance(o.get("object_id"), str)}
    out: List[Dict[str, Any]] = []
    for rel0 in md.relations or []:
        rel = model_dump_compat(rel0)
        if str(rel.get("ref_frame") or "") != "egocentric":
            continue
        a_id = str(rel.get("anchor_id") or "")
        t_id = str(rel.get("target_id") or "")
        if not a_id or not t_id:
            continue
        a = obj_map.get(a_id)
        t = obj_map.get(t_id)
        if not a or not t:
            continue
        comps = _direction_components(rel)
        if not comps:
            continue
        out.append({"rel": rel, "anchor": a, "target": t, "components": comps})
    return out


def generate_spatial_relation_3d_qa_items(md: MetadataV0, *, cfg: SpatialRelation3DConfig) -> List[AnnotationQaItemV0]:
    requested = {k: max(0, int(cfg.sub_tasks.get(k, 0))) for k in STYLE_ORDER}
    if sum(requested.values()) <= 0:
        return []
    candidates = _iter_candidates(md)
    if not candidates:
        return []
    rng = random.Random(cfg.random_seed)

    # deterministic + stable; keep at most one style allocation per relation when shortage happens
    pool = list(candidates)
    rng.shuffle(pool)
    out: List[AnnotationQaItemV0] = []
    qa_idx = 0
    for style in STYLE_ORDER:
        need = requested.get(style, 0)
        if need <= 0:
            continue
        take = pool[:need]
        pool = pool[need:] + pool[:0]
        for c in take:
            rel = c["rel"]
            comps = list(c["components"])
            anchor_txt = _display_name(c["anchor"])
            target_txt = _display_name(c["target"])
            gt_primary = comps[0]
            gt_comp_str = " and ".join(comps)

            if style == ATOMIC:
                q, ans = _build_atomic_qa(anchor_txt, target_txt, gt_primary)
            elif style == COMPOSITE:
                q, ans = _build_composite_qa(anchor_txt, target_txt, gt_comp_str)
            else:
                q, ans, statement = _build_judgment_qa(rng, anchor_txt, target_txt, comps, cfg.judgment_true_prob)

            meta: Dict[str, Any] = {
                "sample_id": md.sample.sample_id,
                "qa_type": "3d_spatial_relation",
                "qa_style": style,
                "ref_frame": "egocentric",
                "relation_id": rel.get("relation_id"),
                "anchor_id": rel.get("anchor_id"),
                "target_id": rel.get("target_id"),
                "anchor_text": anchor_txt,
                "target_text": target_txt,
                "components": comps,
                "predicate": rel.get("predicate"),
                "source": rel.get("source"),
            }
            if style == JUDGMENT:
                meta["statement_direction"] = statement

            out.append(
                AnnotationQaItemV0(
                    qa_id=f"qa#{qa_idx}",
                    task="spatial_relation_3d",
                    question=q,
                    answer=ans,
                    question_type=("judgment" if style == JUDGMENT else "open_ended"),
                    question_tags=["3D Spatial Relation", "Egocentric"],
                    meta=meta,
                    relation_id=str(rel.get("relation_id") or "") or None,
                )
            )
            qa_idx += 1
            record_spatial_relation_3d_qa_stats(
                sample_id=str(md.sample.sample_id),
                qa_style=style,
                gt_direction=gt_comp_str,
            )
    return out


def config_from_params(params: Dict[str, Any]) -> SpatialRelation3DConfig:
    sub = params.get("sub_tasks")
    return SpatialRelation3DConfig(
        random_seed=params.get("random_seed"),
        judgment_true_prob=float(params.get("judgment_true_prob", 0.5)),
        sub_tasks=dict(sub) if isinstance(sub, dict) else _default_sub_tasks(),
    )

