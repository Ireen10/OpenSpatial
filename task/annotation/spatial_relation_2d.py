"""
Generate 2D spatial-relation QA directly from sample-level metadata rows.
"""

import os
import random
from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple

from PIL import Image

from task.base_task import BaseTask
from task.annotation.core.question_type import QuestionType
from task.annotation.core.visual_marker import MarkConfig, VisualMarker
from task.prompt_templates.relation_2d_prompt_templates import (
    FULL_SENTENCE_QUESTION_TEMPLATES,
    JUDGMENT_QUESTION_TEMPLATES,
    SINGLE_AXIS_QUESTION_TEMPLATES,
)
from utils.image_utils import convert_pil_to_bytes


FULL_SENTENCE = "full_sentence"
SINGLE_AXIS = "single_axis"
JUDGMENT = "judgment"

STYLE_PRIORITY = [SINGLE_AXIS, FULL_SENTENCE, JUDGMENT]
DROP_WEIGHTS = {
    SINGLE_AXIS: 1.0,
    FULL_SENTENCE: 2.0,
    JUDGMENT: 4.0,
}

QUESTION_TYPE_BY_STYLE = {
    FULL_SENTENCE: QuestionType.OPEN_ENDED,
    SINGLE_AXIS: QuestionType.MCQ,
    JUDGMENT: QuestionType.OPEN_ENDED,
}

ATOMIC_TO_AXIS = {
    "left": "horizontal",
    "right": "horizontal",
    "above": "vertical",
    "below": "vertical",
}
ATOMIC_OPPOSITE = {
    "left": "right",
    "right": "left",
    "above": "below",
    "below": "above",
}
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
AXIS_OPTIONS = {
    "horizontal": ("left", "right"),
    "vertical": ("above", "below"),
}


class AnnotationGenerator(BaseTask):
    def __init__(self, args):
        super().__init__(args)
        self.rng = random.Random(args.get("random_seed"))
        self.image_root = args.get("image_root")
        self.unique_text_only_prob = float(args.get("unique_text_only_prob", 0.82))
        self.partial_correct_ratio_threshold = float(args.get("partial_correct_ratio_threshold", 0.75))
        self.axis_close_ratio_threshold = float(args.get("axis_close_ratio_threshold", 0.2))
        self.shortage_randomness = float(args.get("shortage_randomness", 0.15))
        self.judgment_distribution = deepcopy(
            args.get(
                "judgment_distribution",
                {"incorrect": 0.5, "partial": 0.15, "correct": 0.35},
            )
        )
        # When both ends need a box (duplicate surface text / crowded tags), keep only a small fraction.
        self.dual_box_keep_prob = float(args.get("dual_box_keep_prob", 0.1))
        # Prefer relation edges that tend to need 0–1 drawn boxes when allocating styles to edges.
        self.prioritize_low_mark_relations = bool(args.get("prioritize_low_mark_relations", True))
        self._sub_tasks_config = self._parse_sub_tasks(args.get("sub_tasks", None))

    def _parse_sub_tasks(self, raw):
        if raw is None or raw == "all":
            return None
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            return {k: None for k in raw}
        if hasattr(raw, "__dict__"):
            return vars(raw)
        raise ValueError(f"Invalid sub_tasks config: {raw}")

    def get_sub_task_count(self, sub_task: str, default: int = 1) -> int:
        if self._sub_tasks_config is None:
            return default
        if sub_task not in self._sub_tasks_config:
            return 0
        count = self._sub_tasks_config[sub_task]
        return default if count is None else int(count)

    def check_example(self, example) -> bool:
        sample = example.get("sample")
        return (
            isinstance(sample, dict)
            and isinstance(sample.get("image"), dict)
            and isinstance(example.get("objects"), list)
            and isinstance(example.get("relations"), list)
        )

    def apply_transform(self, example, idx=None):
        if not self.check_example(example):
            return None, False

        image_path = self._resolve_image_path(example)
        if image_path is None or not os.path.isfile(image_path):
            return None, False

        candidate_relations, object_map = self._collect_candidate_relations(example)
        if not candidate_relations:
            return None, False

        with Image.open(image_path) as img_f:
            image = img_f.convert("RGB").copy()

        requested = {
            SINGLE_AXIS: self.get_sub_task_count(SINGLE_AXIS, default=1),
            FULL_SENTENCE: self.get_sub_task_count(FULL_SENTENCE, default=1),
            JUDGMENT: self.get_sub_task_count(JUDGMENT, default=1),
        }
        plan = self._plan_counts(requested, len(candidate_relations))
        allocations = self._allocate_relations(candidate_relations, plan)

        questions, answers, metas, qa_images = [], [], [], []
        question_types, question_tags = [], []

        for style in STYLE_PRIORITY:
            for rel in allocations.get(style, []):
                qa = self._build_qa(style, rel, object_map, image, example)
                if qa is None:
                    continue
                question, answer, meta, qa_image = qa
                questions.append(question)
                answers.append(answer)
                metas.append(meta)
                qa_images.append(qa_image)
                question_types.append(QUESTION_TYPE_BY_STYLE[style])
                question_tags.append(["2D Spatial Relation"])

        if not questions:
            return None, False

        example["image"] = image_path
        example["question"] = questions
        example["answer"] = answers
        example["meta"] = metas
        example["QA_images"] = qa_images
        example["question_types"] = question_types
        example["question_tags"] = question_tags
        return example, True

    def _resolve_image_path(self, example) -> Optional[str]:
        top_level = example.get("image")
        if isinstance(top_level, str) and top_level:
            if os.path.isfile(top_level):
                return top_level
            if self.image_root and not os.path.isabs(top_level):
                joined = os.path.join(self.image_root, top_level)
                if os.path.isfile(joined):
                    return joined

        rel_path = (((example.get("sample") or {}).get("image") or {}).get("path"))
        if not isinstance(rel_path, str) or not rel_path:
            return None
        if os.path.isabs(rel_path) and os.path.isfile(rel_path):
            return rel_path
        if self.image_root:
            return os.path.join(self.image_root, rel_path)
        return rel_path if os.path.isfile(rel_path) else None

    def _collect_candidate_relations(self, example) -> Tuple[List[dict], Dict[str, dict]]:
        object_map = {obj["object_id"]: obj for obj in example.get("objects", []) if isinstance(obj, dict) and obj.get("object_id")}
        name_counts: Dict[str, int] = {}
        for obj in object_map.values():
            name = self._display_name(obj)
            name_counts[name] = name_counts.get(name, 0) + 1

        candidates = []
        for rel in example.get("relations", []):
            if not isinstance(rel, dict):
                continue
            if rel.get("ref_frame") != "image_plane":
                continue
            anchor = object_map.get(rel.get("anchor_id"))
            target = object_map.get(rel.get("target_id"))
            if anchor is None or target is None:
                continue
            if not rel.get("relation_id"):
                continue
            if not self._is_relation_usable(anchor, target, name_counts):
                continue
            if self._pair_unmarkable(anchor, target, name_counts):
                continue
            candidates.append(rel)

        if self.prioritize_low_mark_relations:
            buckets: Dict[int, List[dict]] = defaultdict(list)
            for rel in candidates:
                a = object_map[rel["anchor_id"]]
                b = object_map[rel["target_id"]]
                buckets[self._mark_tier(a, b, name_counts)].append(rel)
            candidates = []
            for tier in (0, 1, 2):
                tier_list = buckets[tier]
                self.rng.shuffle(tier_list)
                candidates.extend(tier_list)
        else:
            self.rng.shuffle(candidates)
        return candidates, object_map

    def _is_relation_usable(self, anchor: dict, target: dict, name_counts: Dict[str, int]) -> bool:
        same_category = (
            bool(anchor.get("category"))
            and anchor.get("category") == target.get("category")
        )
        if not same_category:
            return True
        return self._can_disambiguate(anchor, name_counts) and self._can_disambiguate(target, name_counts)

    def _can_disambiguate(self, obj: dict, name_counts: Dict[str, int]) -> bool:
        name = self._display_name(obj)
        if name_counts.get(name, 0) == 1:
            return True
        return self._bbox_of(obj) is not None

    def _plan_counts(self, requested: Dict[str, int], n_edges: int) -> Dict[str, int]:
        planned = {k: max(0, int(v)) for k, v in requested.items()}
        while sum(planned.values()) > n_edges:
            candidates = [k for k, v in planned.items() if v > 0]
            if not candidates:
                break
            weights = []
            for name in candidates:
                base = DROP_WEIGHTS[name]
                jitter = self.rng.uniform(0.0, self.shortage_randomness)
                weights.append(base + jitter)
            to_reduce = self.rng.choices(candidates, weights=weights, k=1)[0]
            planned[to_reduce] -= 1
        return planned

    def _allocate_relations(self, relations: List[dict], plan: Dict[str, int]) -> Dict[str, List[dict]]:
        remaining = list(relations)
        out = {FULL_SENTENCE: [], SINGLE_AXIS: [], JUDGMENT: []}
        for style in STYLE_PRIORITY:
            need = plan.get(style, 0)
            if need <= 0:
                continue
            out[style] = remaining[:need]
            remaining = remaining[need:]
        return out

    def _build_qa(self, style: str, rel: dict, object_map: Dict[str, dict], image: Image.Image, example: dict):
        anchor = object_map[rel["anchor_id"]]
        target = object_map[rel["target_id"]]
        name_counts = self._name_counts(object_map)
        roles_to_mark = self._predict_roles_to_mark(anchor, target, name_counts)
        if roles_to_mark is None:
            return None
        if len(roles_to_mark) >= 2 and self.rng.random() >= self.dual_box_keep_prob:
            return None
        anchor_text, target_text, qa_image, marker_meta = self._materialize_refs(anchor, target, image, roles_to_mark)

        if style == FULL_SENTENCE:
            question, answer = self._build_full_sentence(anchor_text, target_text, rel)
        elif style == SINGLE_AXIS:
            question, answer, extra = self._build_single_axis(anchor_text, target_text, rel)
            marker_meta.update(extra)
        else:
            question, answer, extra = self._build_judgment(anchor_text, target_text, rel)
            marker_meta.update(extra)

        meta = {
            "sample_id": ((example.get("sample") or {}).get("sample_id")),
            "relation_id": rel["relation_id"],
            "qa_type": "2d_spatial_relation",
            "qa_style": style,
            "anchor_id": anchor["object_id"],
            "target_id": target["object_id"],
            "anchor_text": self._display_name(anchor),
            "target_text": self._display_name(target),
            "predicate": rel.get("predicate"),
            "components": list(rel.get("components") or []),
            "ref_frame": rel.get("ref_frame"),
            "marked_roles": marker_meta["marked_roles"],
            "mark_colors": marker_meta["mark_colors"],
            "mark_tier": self._mark_tier(anchor, target, name_counts),
            "n_marked_boxes": len(marker_meta.get("marked_roles") or []),
        }
        if "axis" in marker_meta:
            meta["axis"] = marker_meta["axis"]
        if "judgment_mode" in marker_meta:
            meta["judgment_mode"] = marker_meta["judgment_mode"]
        if "statement_direction" in marker_meta:
            meta["statement_direction"] = marker_meta["statement_direction"]
        meta["same_surface_description"] = bool(marker_meta.get("same_surface_description"))
        if meta["same_surface_description"] and marker_meta.get("shared_description"):
            meta["shared_description"] = marker_meta["shared_description"]
        return question, answer, meta, qa_image

    def _name_counts(self, object_map: Dict[str, dict]) -> Dict[str, int]:
        name_counts: Dict[str, int] = {}
        for obj in object_map.values():
            name = self._display_name(obj)
            name_counts[name] = name_counts.get(name, 0) + 1
        return name_counts

    @staticmethod
    def _pair_unmarkable(anchor: dict, target: dict, name_counts: Dict[str, int]) -> bool:
        """True if disambiguation would require a box but geometry is missing (do not use RNG)."""
        da = AnnotationGenerator._display_name(anchor)
        dt = AnnotationGenerator._display_name(target)
        if name_counts.get(da, 0) != 1 and AnnotationGenerator._bbox_of(anchor) is None:
            return True
        if name_counts.get(dt, 0) != 1 and AnnotationGenerator._bbox_of(target) is None:
            return True
        return False

    @staticmethod
    def _mark_tier(anchor: dict, target: dict, name_counts: Dict[str, int]) -> int:
        """Deterministic preference rank: lower tier tends to need fewer drawn boxes."""
        da = AnnotationGenerator._display_name(anchor)
        dt = AnnotationGenerator._display_name(target)
        au = name_counts.get(da, 0) == 1
        tu = name_counts.get(dt, 0) == 1
        if au and tu:
            return 0
        if au or tu:
            return 1
        return 2

    def _predict_roles_to_mark(
        self, anchor: dict, target: dict, name_counts: Dict[str, int]
    ) -> Optional[Set[str]]:
        anchor_unique = name_counts[self._display_name(anchor)] == 1
        target_unique = name_counts[self._display_name(target)] == 1

        marked_roles: Set[str] = set()
        if anchor_unique and target_unique:
            if self.rng.random() < self.unique_text_only_prob:
                return marked_roles
            role = self.rng.choice(["anchor", "target"])
            obj = anchor if role == "anchor" else target
            if self._bbox_of(obj) is None:
                return marked_roles
            marked_roles.add(role)
            return marked_roles

        if not anchor_unique:
            if self._bbox_of(anchor) is None:
                return None
            marked_roles.add("anchor")
        if not target_unique:
            if self._bbox_of(target) is None:
                return None
            marked_roles.add("target")
        return marked_roles

    @staticmethod
    def _box_colors_in_draw_order(n: int) -> List[str]:
        """Match VisualMarker color queue order for the first n boxed objects."""
        marker = VisualMarker(MarkConfig(mark_types=["box"]))
        return [marker.pop_color()[0] for _ in range(n)]

    @staticmethod
    def _box_ref_suffix(color_name: str) -> str:
        """English disambiguation note aligned with colored box outlines (no A/B letters on image)."""
        return f"(the object in the {color_name} box in the image)"

    @staticmethod
    def _same_surface_description(anchor: dict, target: dict) -> bool:
        a = AnnotationGenerator._display_name(anchor).strip().lower()
        b = AnnotationGenerator._display_name(target).strip().lower()
        return bool(a) and a == b

    def _materialize_refs(self, anchor: dict, target: dict, image: Image.Image, roles_to_mark: Set[str]):
        anchor_name = self._display_name(anchor)
        target_name = self._display_name(target)
        same_phrase = self._same_surface_description(anchor, target)
        if not roles_to_mark:
            return anchor_name, target_name, {"bytes": convert_pil_to_bytes(image)}, {
                "marked_roles": [],
                "mark_colors": {},
                "same_surface_description": same_phrase,
                "shared_description": anchor_name if same_phrase else None,
            }

        ordered_roles = [r for r in ("anchor", "target") if r in roles_to_mark]
        colors = self._box_colors_in_draw_order(len(ordered_roles))
        role_to_color = {role: colors[i] for i, role in enumerate(ordered_roles)}

        objs = []
        for role in ordered_roles:
            obj = anchor if role == "anchor" else target
            objs.append((self._display_name(obj), obj, self._bbox_of(obj), None))

        marker = VisualMarker(MarkConfig(mark_types=["box"]))
        qa_image, _ = marker.mark_objects(image, objs=objs, mark_type="box")

        meta_extra: Dict[str, Any] = {
            "same_surface_description": same_phrase,
            "shared_description": anchor_name.strip() if same_phrase else None,
        }

        if (
            same_phrase
            and role_to_color.get("anchor")
            and role_to_color.get("target")
        ):
            ca = role_to_color["anchor"]
            ct = role_to_color["target"]
            anchor_name = f"the object in the {ca} box"
            target_name = f"the object in the {ct} box"
        else:
            if "anchor" in role_to_color:
                anchor_name = f"{anchor_name} {self._box_ref_suffix(role_to_color['anchor'])}"
            if "target" in role_to_color:
                target_name = f"{target_name} {self._box_ref_suffix(role_to_color['target'])}"

        return anchor_name, target_name, qa_image, {
            "marked_roles": list(role_to_color.keys()),
            "mark_colors": role_to_color,
            **meta_extra,
        }

    def _build_full_sentence(self, anchor_text: str, target_text: str, rel: dict) -> Tuple[str, str]:
        direction = self._direction_phrase(rel)
        question = self.rng.choice(FULL_SENTENCE_QUESTION_TEMPLATES).format(
            target=target_text,
            anchor=anchor_text,
        )
        answer = f"In the image plane, {target_text} is {direction} {anchor_text}."
        return question, answer

    def _build_single_axis(self, anchor_text: str, target_text: str, rel: dict):
        axis, truth = self._choose_axis_for_relation(rel)
        option_a, option_b = AXIS_OPTIONS[axis]
        if self.rng.random() < 0.5:
            option_a, option_b = option_b, option_a
        answer = "A" if truth == option_a else "B"
        question = self.rng.choice(SINGLE_AXIS_QUESTION_TEMPLATES).format(
            target=target_text,
            anchor=anchor_text,
            axis_name=axis,
            option_a=option_a,
            option_b=option_b,
        )
        return question, answer, {"axis": axis}

    def _build_judgment(self, anchor_text: str, target_text: str, rel: dict):
        mode = self._sample_judgment_mode(rel)
        true_direction = self._direction_phrase(rel)
        if mode == "correct":
            statement_direction = true_direction
            answer = "Correct."
        elif mode == "partial":
            _, atom = self._choose_axis_for_relation(rel)
            statement_direction = DIR_PHRASE[(atom,)]
            answer = f"Partially correct. In the image plane, {target_text} is {true_direction} {anchor_text}."
        else:
            statement_direction = DIR_OPPOSITE[true_direction]
            answer = f"Incorrect. In the image plane, {target_text} is {true_direction} {anchor_text}."

        statement = f"{target_text} is {statement_direction} {anchor_text} in the image plane."
        question = self.rng.choice(JUDGMENT_QUESTION_TEMPLATES).format(
            target=target_text,
            anchor=anchor_text,
            statement=statement,
        )
        return question, answer, {
            "judgment_mode": mode,
            "statement_direction": statement_direction,
        }

    def _sample_judgment_mode(self, rel: dict) -> str:
        modes = []
        weights = []
        allow_partial = self._allow_partial(rel)
        for key in ["incorrect", "partial", "correct"]:
            if key == "partial" and not allow_partial:
                continue
            modes.append(key)
            weights.append(float(self.judgment_distribution.get(key, 0.0)))
        if not modes:
            return "incorrect"
        return self.rng.choices(modes, weights=weights, k=1)[0]

    def _allow_partial(self, rel: dict) -> bool:
        components = rel.get("components") or []
        if len(components) != 2:
            return False
        du, dv = self._delta_uv(rel)
        if du is None or dv is None:
            return False
        adu, adv = abs(du), abs(dv)
        if adu == 0 or adv == 0:
            return False
        ratio = min(adu, adv) / max(adu, adv)
        return ratio >= self.partial_correct_ratio_threshold

    def _choose_axis_for_relation(self, rel: dict) -> Tuple[str, str]:
        components = list(rel.get("components") or [])
        if len(components) == 2:
            du, dv = self._delta_uv(rel)
            adu = abs(du) if du is not None else 0
            adv = abs(dv) if dv is not None else 0
            if max(adu, adv) == 0:
                chosen = self.rng.choice(components)
            else:
                max_delta = max(adu, adv)
                close = abs(adu - adv) / max_delta <= self.axis_close_ratio_threshold
                if close:
                    chosen = self.rng.choices(
                        [components[0], components[1]],
                        weights=[adu or 1.0, adv or 1.0],
                        k=1,
                    )[0]
                else:
                    chosen = components[0] if adu >= adv else components[1]
        else:
            chosen = components[0] if components else rel.get("predicate", "left")
        return ATOMIC_TO_AXIS[chosen], chosen

    @staticmethod
    def _delta_uv(rel: dict) -> Tuple[Optional[float], Optional[float]]:
        evidence = rel.get("evidence") or {}
        delta = evidence.get("delta_uv")
        if isinstance(delta, list) and len(delta) == 2:
            return float(delta[0]), float(delta[1])
        return None, None

    @staticmethod
    def _bbox_of(obj: dict):
        bbox = obj.get("bbox_xyxy_norm_1000")
        return bbox if isinstance(bbox, list) and len(bbox) == 4 else None

    @staticmethod
    def _display_name(obj: dict) -> str:
        for key in ["phrase", "category", "object_id"]:
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "object"

    @staticmethod
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
