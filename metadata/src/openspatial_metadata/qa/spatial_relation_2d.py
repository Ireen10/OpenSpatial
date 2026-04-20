"""
Generate 2D spatial-relation QA from ``MetadataV0`` (relations in image_plane).

This module is metadata-native:
- does NOT render or emit image bytes
- emits ``AnnotationQaItemV0`` with enough meta to re-render later (anchor/target ids, mark colors, etc.)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from openspatial_metadata.schema.metadata_v0 import AnnotationQaItemV0, MetadataV0
from openspatial_metadata.prompt_templates import spatial_relation_2d_prompt_templates as tpl


FULL_SENTENCE = "full_sentence"
SINGLE_AXIS = "single_axis"
JUDGMENT = "judgment"

STYLE_PRIORITY = [SINGLE_AXIS, FULL_SENTENCE, JUDGMENT]
DROP_WEIGHTS = {SINGLE_AXIS: 1.0, FULL_SENTENCE: 2.0, JUDGMENT: 4.0}

ATOMIC_TO_AXIS = {"left": "horizontal", "right": "horizontal", "above": "vertical", "below": "vertical"}
DIR_PHRASE = {
    ("left",): "to the left of",
    ("right",): "to the right of",
    ("above",): "above",
    ("below",): "below",
    ("left", "above"): "to the upper left of",
    ("left", "below"): "to the lower left of",
    ("right", "above"): "to the upper right of",
    ("right", "below"): "to the lower right of",
}
DIR_OPPOSITE = {
    "to the left of": "to the right of",
    "to the right of": "to the left of",
    "above": "below",
    "below": "above",
    "to the upper left of": "to the lower right of",
    "to the lower right of": "to the upper left of",
    "to the upper right of": "to the lower left of",
    "to the lower left of": "to the upper right of",
}
AXIS_OPTIONS = {"horizontal": ("left", "right"), "vertical": ("above", "below")}

# Match VisualMarker default color queue order for box marks.
COLOR_QUEUE_DEFAULT = ["red", "blue", "green", "pink", "yellow", "orange", "purple", "brown"]


def _default_sub_tasks() -> Dict[str, int]:
    return {SINGLE_AXIS: 1, FULL_SENTENCE: 1, JUDGMENT: 1}


@dataclass(frozen=True)
class SpatialRelation2DConfig:
    random_seed: Optional[int] = 7
    unique_text_only_prob: float = 0.82
    dual_box_keep_prob: float = 0.1
    prioritize_low_mark_relations: bool = True
    partial_correct_ratio_threshold: float = 0.75
    axis_close_ratio_threshold: float = 0.2
    shortage_randomness: float = 0.15
    judgment_distribution: Optional[Dict[str, float]] = None
    sub_tasks: Dict[str, int] = field(default_factory=_default_sub_tasks)

    def __post_init__(self):
        if self.judgment_distribution is None:
            object.__setattr__(self, "judgment_distribution", {"incorrect": 0.5, "partial": 0.15, "correct": 0.35})


def generate_spatial_relation_2d_qa_items(md: MetadataV0, *, cfg: SpatialRelation2DConfig) -> List[AnnotationQaItemV0]:
    rng = random.Random(cfg.random_seed)

    objects = [o.dict() if hasattr(o, "dict") else o.model_dump() for o in (md.objects or [])]
    object_map = {o.get("object_id"): o for o in objects if isinstance(o, dict) and isinstance(o.get("object_id"), str)}
    name_counts: Dict[str, int] = {}
    for o in object_map.values():
        n = _display_name(o)
        name_counts[n] = name_counts.get(n, 0) + 1

    candidates: List[dict] = []
    for rel in (md.relations or []):
        r = rel.dict() if hasattr(rel, "dict") else rel.model_dump()
        if r.get("ref_frame") != "image_plane":
            continue
        if not r.get("relation_id"):
            continue
        a = object_map.get(r.get("anchor_id"))
        t = object_map.get(r.get("target_id"))
        if not a or not t:
            continue
        if not _is_relation_usable(a, t, name_counts):
            continue
        if _pair_unmarkable(a, t, name_counts):
            continue
        candidates.append(r)

    if not candidates:
        return []

    if cfg.prioritize_low_mark_relations:
        candidates.sort(key=lambda r: _mark_tier(object_map[r["anchor_id"]], object_map[r["target_id"]], name_counts))

    requested = {
        SINGLE_AXIS: max(0, int(cfg.sub_tasks.get(SINGLE_AXIS, 0))),
        FULL_SENTENCE: max(0, int(cfg.sub_tasks.get(FULL_SENTENCE, 0))),
        JUDGMENT: max(0, int(cfg.sub_tasks.get(JUDGMENT, 0))),
    }
    plan = _plan_counts(rng, requested, len(candidates), cfg.shortage_randomness)
    alloc = _allocate_relations(candidates, plan)

    out: List[AnnotationQaItemV0] = []
    qa_index = 0
    for style in STYLE_PRIORITY:
        for rel in alloc.get(style, []):
            a = object_map[rel["anchor_id"]]
            t = object_map[rel["target_id"]]
            roles_to_mark = _predict_roles_to_mark(rng, cfg, a, t, name_counts)
            if roles_to_mark is None:
                continue
            if len(roles_to_mark) >= 2 and rng.random() >= cfg.dual_box_keep_prob:
                continue

            anchor_text, target_text, marker_meta = _materialize_refs(rng, a, t, roles_to_mark)
            if style == FULL_SENTENCE:
                direction = _direction_phrase(rel)
                q, ans, inst_mode, ans_mode = tpl.render_full_sentence_qa_pair_with_modes(
                    rng, anchor=anchor_text, target=target_text, direction=direction
                )
                marker_meta["instruction_mode"] = inst_mode
                marker_meta["answer_mode"] = ans_mode
            elif style == SINGLE_AXIS:
                q, ans, extra = _build_single_axis(rng, cfg, anchor_text, target_text, rel)
                marker_meta.update(extra)
            else:
                q, ans, extra = _build_judgment(rng, cfg, anchor_text, target_text, rel)
                marker_meta.update(extra)
                # Currently judgment has a single instruction mode in templates.
                marker_meta.setdefault("instruction_mode", "with_explanation")
                marker_meta.setdefault("answer_mode", "with_explanation")

            meta = {
                "sample_id": md.sample.sample_id,
                "relation_id": rel["relation_id"],
                "qa_type": "2d_spatial_relation",
                "qa_style": style,
                "anchor_id": a["object_id"],
                "target_id": t["object_id"],
                "anchor_text": _display_name(a),
                "target_text": _display_name(t),
                "predicate": rel.get("predicate"),
                "components": list(rel.get("components") or []),
                "ref_frame": rel.get("ref_frame"),
                "marked_roles": marker_meta["marked_roles"],
                "mark_colors": marker_meta["mark_colors"],
                "mark_tier": _mark_tier(a, t, name_counts),
                "n_marked_boxes": len(marker_meta.get("marked_roles") or []),
                "same_surface_description": bool(marker_meta.get("same_surface_description")),
            }
            if marker_meta.get("shared_description"):
                meta["shared_description"] = marker_meta["shared_description"]
            for k in ("axis", "judgment_mode", "statement_direction", "instruction_mode", "answer_mode"):
                if k in marker_meta:
                    meta[k] = marker_meta[k]

            out.append(
                AnnotationQaItemV0(
                    qa_id=f"qa#{qa_index}",
                    task="spatial_relation_2d",
                    question=q,
                    answer=ans,
                    question_type=("MCQ" if style == SINGLE_AXIS else "open_ended"),
                    question_tags=["2D Spatial Relation"],
                    meta=meta,
                    relation_id=rel.get("relation_id"),
                )
            )
            qa_index += 1

    return out


def config_from_params(params: Dict[str, Any]) -> SpatialRelation2DConfig:
    """Build ``SpatialRelation2DConfig`` from a mapping (e.g. qa_tasks.yaml params + overrides)."""
    jd = params.get("judgment_distribution")
    st = params.get("sub_tasks")
    return SpatialRelation2DConfig(
        random_seed=params.get("random_seed"),
        unique_text_only_prob=float(params.get("unique_text_only_prob", 0.82)),
        dual_box_keep_prob=float(params.get("dual_box_keep_prob", 0.1)),
        prioritize_low_mark_relations=bool(params.get("prioritize_low_mark_relations", True)),
        partial_correct_ratio_threshold=float(params.get("partial_correct_ratio_threshold", 0.75)),
        axis_close_ratio_threshold=float(params.get("axis_close_ratio_threshold", 0.2)),
        shortage_randomness=float(params.get("shortage_randomness", 0.15)),
        judgment_distribution=dict(jd) if isinstance(jd, dict) else None,
        sub_tasks=dict(st) if isinstance(st, dict) else _default_sub_tasks(),
    )


def _plan_counts(rng: random.Random, requested: Dict[str, int], n_edges: int, jitter: float) -> Dict[str, int]:
    planned = {k: max(0, int(v)) for k, v in requested.items()}
    while sum(planned.values()) > n_edges:
        candidates = [k for k, v in planned.items() if v > 0]
        if not candidates:
            break
        weights = []
        for name in candidates:
            weights.append(DROP_WEIGHTS[name] + rng.uniform(0.0, float(jitter)))
        to_reduce = rng.choices(candidates, weights=weights, k=1)[0]
        planned[to_reduce] -= 1
    return planned


def _allocate_relations(relations: List[dict], plan: Dict[str, int]) -> Dict[str, List[dict]]:
    remaining = list(relations)
    out = {FULL_SENTENCE: [], SINGLE_AXIS: [], JUDGMENT: []}
    for style in STYLE_PRIORITY:
        need = plan.get(style, 0)
        if need <= 0:
            continue
        out[style] = remaining[:need]
        remaining = remaining[need:]
    return out


def _bbox_of(obj: dict):
    bbox = obj.get("bbox_xyxy_norm_1000")
    return bbox if isinstance(bbox, list) and len(bbox) == 4 else None


def _display_name(obj: dict) -> str:
    for key in ["phrase", "category", "object_id"]:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "object"


def _same_surface_description(anchor: dict, target: dict) -> bool:
    a = _display_name(anchor).strip().lower()
    b = _display_name(target).strip().lower()
    return bool(a) and a == b


def _is_relation_usable(anchor: dict, target: dict, name_counts: Dict[str, int]) -> bool:
    # If both are unique by text, always usable.
    if name_counts.get(_display_name(anchor), 0) == 1 and name_counts.get(_display_name(target), 0) == 1:
        return True
    # Otherwise we need geometry for at least the non-unique sides that we may box.
    return _bbox_of(anchor) is not None or _bbox_of(target) is not None


def _pair_unmarkable(anchor: dict, target: dict, name_counts: Dict[str, int]) -> bool:
    da = _display_name(anchor)
    dt = _display_name(target)
    if name_counts.get(da, 0) == 1 and name_counts.get(dt, 0) == 1:
        return False
    if name_counts.get(da, 0) > 1 and _bbox_of(anchor) is None:
        return True
    if name_counts.get(dt, 0) > 1 and _bbox_of(target) is None:
        return True
    return False


def _mark_tier(anchor: dict, target: dict, name_counts: Dict[str, int]) -> int:
    da = _display_name(anchor)
    dt = _display_name(target)
    au = name_counts.get(da, 0) == 1
    tu = name_counts.get(dt, 0) == 1
    if au and tu:
        return 0
    if au or tu:
        return 1
    return 2


def _predict_roles_to_mark(
    rng: random.Random, cfg: SpatialRelation2DConfig, anchor: dict, target: dict, name_counts: Dict[str, int]
) -> Optional[Set[str]]:
    anchor_unique = name_counts[_display_name(anchor)] == 1
    target_unique = name_counts[_display_name(target)] == 1

    marked_roles: Set[str] = set()
    if anchor_unique and target_unique:
        if rng.random() < float(cfg.unique_text_only_prob):
            return marked_roles
        role = rng.choice(["anchor", "target"])
        obj = anchor if role == "anchor" else target
        if _bbox_of(obj) is None:
            return marked_roles
        marked_roles.add(role)
        return marked_roles

    if not anchor_unique:
        if _bbox_of(anchor) is None:
            return None
        marked_roles.add("anchor")
    if not target_unique:
        if _bbox_of(target) is None:
            return None
        marked_roles.add("target")
    return marked_roles


def _materialize_refs(rng: random.Random, anchor: dict, target: dict, roles_to_mark: Set[str]):
    anchor_name = _display_name(anchor)
    target_name = _display_name(target)
    same_phrase = _same_surface_description(anchor, target)

    if not roles_to_mark:
        return anchor_name, target_name, {
            "marked_roles": [],
            "mark_colors": {},
            "same_surface_description": same_phrase,
            "shared_description": anchor_name if same_phrase else None,
        }

    ordered_roles = [r for r in ("anchor", "target") if r in roles_to_mark]
    colors = [COLOR_QUEUE_DEFAULT[i] for i in range(len(ordered_roles))]
    role_to_color = {role: colors[i] for i, role in enumerate(ordered_roles)}

    meta_extra: Dict[str, Any] = {
        "same_surface_description": same_phrase,
        "shared_description": anchor_name.strip() if same_phrase else None,
    }

    if same_phrase and role_to_color.get("anchor") and role_to_color.get("target"):
        ca = role_to_color["anchor"]
        ct = role_to_color["target"]
        anchor_name = tpl.render_marked_ref_same_phrase(rng, color=ca)
        target_name = tpl.render_marked_ref_same_phrase(rng, color=ct)
    else:
        if "anchor" in role_to_color:
            anchor_name = tpl.render_marked_ref_with_hint(rng, name=anchor_name, color=role_to_color["anchor"])
        if "target" in role_to_color:
            target_name = tpl.render_marked_ref_with_hint(rng, name=target_name, color=role_to_color["target"])

    return anchor_name, target_name, {
        "marked_roles": list(role_to_color.keys()),
        "mark_colors": role_to_color,
        **meta_extra,
    }


def _direction_phrase(rel: dict) -> str:
    components = list(rel.get("components") or [])
    if components:
        key = tuple(components)
        if key in DIR_PHRASE:
            return DIR_PHRASE[key]
    predicate = rel.get("predicate")
    if predicate in ATOMIC_TO_AXIS:
        return DIR_PHRASE[(predicate,)]
    return "near"


def _delta_uv(rel: dict) -> Tuple[Optional[float], Optional[float]]:
    evidence = rel.get("evidence") or {}
    if not isinstance(evidence, dict):
        return None, None
    # Prefer our enrich output shape: {"delta_uv": [du, dv]}
    duv = evidence.get("delta_uv")
    if isinstance(duv, (list, tuple)) and len(duv) == 2:
        du, dv = duv[0], duv[1]
        return (
            float(du) if isinstance(du, (int, float)) else None,
            float(dv) if isinstance(dv, (int, float)) else None,
        )

    # Back-compat / alternate shape
    du = evidence.get("delta_u")
    dv = evidence.get("delta_v")
    return (
        float(du) if isinstance(du, (int, float)) else None,
        float(dv) if isinstance(dv, (int, float)) else None,
    )


def _allow_partial(cfg: SpatialRelation2DConfig, rel: dict) -> bool:
    components = rel.get("components") or []
    if len(components) != 2:
        return False
    du, dv = _delta_uv(rel)
    if du is None or dv is None:
        return False
    adu, adv = abs(du), abs(dv)
    if adu == 0 or adv == 0:
        return False
    ratio = min(adu, adv) / max(adu, adv)
    return ratio >= float(cfg.partial_correct_ratio_threshold)


def _choose_axis_for_relation(cfg: SpatialRelation2DConfig, rng: random.Random, rel: dict) -> Tuple[str, str]:
    components = list(rel.get("components") or [])
    if len(components) == 2:
        du, dv = _delta_uv(rel)
        adu = abs(du) if du is not None else 0
        adv = abs(dv) if dv is not None else 0
        if max(adu, adv) == 0:
            chosen = rng.choice(components)
        else:
            max_delta = max(adu, adv)
            close = abs(adu - adv) / max_delta <= float(cfg.axis_close_ratio_threshold)
            if close:
                chosen = rng.choices([components[0], components[1]], weights=[adu or 1.0, adv or 1.0], k=1)[0]
            else:
                chosen = components[0] if adu >= adv else components[1]
    else:
        chosen = components[0] if components else rel.get("predicate", "left")
    return ATOMIC_TO_AXIS.get(chosen, "horizontal"), str(chosen)


def _build_single_axis(
    rng: random.Random, cfg: SpatialRelation2DConfig, anchor_text: str, target_text: str, rel: dict
) -> Tuple[str, str, Dict[str, Any]]:
    axis, truth_atom = _choose_axis_for_relation(cfg, rng, rel)
    option_a, option_b = AXIS_OPTIONS[axis]
    if rng.random() < 0.5:
        option_a, option_b = option_b, option_a
    truth = truth_atom
    question, answer, inst_mode, ans_mode = tpl.render_single_axis_qa_pair_with_modes(
        rng,
        anchor=anchor_text,
        target=target_text,
        axis_name=axis,
        option_a=option_a,
        option_b=option_b,
        truth=truth,
    )
    return question, answer, {"axis": axis, "instruction_mode": inst_mode, "answer_mode": ans_mode}


def _sample_judgment_mode(rng: random.Random, cfg: SpatialRelation2DConfig, rel: dict) -> str:
    modes = []
    weights = []
    allow_partial = _allow_partial(cfg, rel)
    for key in ["incorrect", "partial", "correct"]:
        if key == "partial" and not allow_partial:
            continue
        modes.append(key)
        weights.append(float(cfg.judgment_distribution.get(key, 0.0)))
    if not modes:
        return "incorrect"
    return rng.choices(modes, weights=weights, k=1)[0]


def _build_judgment(
    rng: random.Random, cfg: SpatialRelation2DConfig, anchor_text: str, target_text: str, rel: dict
) -> Tuple[str, str, Dict[str, Any]]:
    mode = _sample_judgment_mode(rng, cfg, rel)
    true_direction = _direction_phrase(rel)
    if mode == "correct":
        statement_direction = true_direction
    elif mode == "partial":
        _, atom = _choose_axis_for_relation(cfg, rng, rel)
        statement_direction = DIR_PHRASE.get((atom,), true_direction)
    else:
        statement_direction = DIR_OPPOSITE.get(true_direction, true_direction)
    statement = tpl.render_judgment_statement(anchor=anchor_text, target=target_text, statement_direction=statement_direction)
    question = tpl.render_judgment_question(rng, anchor=anchor_text, target=target_text, statement=statement)
    answer = tpl.render_judgment_answer(rng, mode=mode, anchor=anchor_text, target=target_text, true_direction=true_direction)
    return question, answer, {"judgment_mode": mode, "statement_direction": statement_direction}

