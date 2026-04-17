from __future__ import annotations

import random
from typing import Dict, Tuple

"""
Prompt template design intent (for maintainers):

We build prompts from 3 optional parts:

1) task description (distinguish 2D image-plane vs 3D spatial reasoning)
2) question template (the main query)
3) instruction-following (optional, per question type)

Goal: after wiring is done, prompt diversity work should mostly edit the candidate pools below,
without touching QA generation logic.
"""


# ----------------------------
# Shared helpers (do not edit unless needed)
# ----------------------------

def _cap_first(s: str) -> str:
    s2 = (s or "").strip()
    if not s2:
        return s2
    return s2[0].upper() + s2[1:]


def _join_parts(parts: list[str]) -> str:
    xs = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    return "\n\n".join(xs)


def _fmt(s: str, **kwargs: str) -> str:
    """
    Format helper with optional capitalization variants.
    Provides:
    - anchor / target
    - Anchor / Target (cap-first)
    """
    return s.format(
        **kwargs,
        Anchor=_cap_first(kwargs.get("anchor", "")),
        Target=_cap_first(kwargs.get("target", "")),
    )


# ----------------------------
# Candidate pools (edit these for diversity)
# ----------------------------

# 1) Task description pools (shared across styles)
TASK_DESCRIPTION_POOL = [
    "You are given an image. Focus ONLY on the 2D image plane (pixel-space) positions when answering.",
    "Answer based on the 2D image plane locations of the objects (ignore any 3D/real-world depth assumptions).",
]

# 2) Question template pools (per style)
FULL_SENTENCE_QUESTION_POOL = [
    "Determine the 2D spatial relation between {target} and {anchor} in the image plane.",
    "Based on their locations in the image plane, describe where {target} is with respect to {anchor}.",
    "Look only at the 2D image plane and state the relative position of {target} with respect to {anchor}.",
]

SINGLE_AXIS_QUESTION_POOL = [
    "In the image plane, compare {target} and {anchor} along the {axis_name} direction. Where is {target} relative to {anchor}?\nOptions: A. {option_a} B. {option_b}",
    "Along the {axis_name} axis in the image, where is {target} with respect to {anchor}?\nOptions: A. {option_a} B. {option_b}",
]

JUDGMENT_QUESTION_POOL = [
    "In the 2D image plane, judge whether this statement is correct: {statement}.",
    "Based only on the image-plane positions, evaluate this statement: {statement}.",
]

# 3) Instruction-following pools (per style)
FULL_SENTENCE_INSTRUCTION_POOL = [
    # Optional: leave empty to allow free-form answers.
    "Answer with one complete sentence.",
]

SINGLE_AXIS_INSTRUCTION_POOL = [
    "Respond with ONLY the letter A or B.",
]

JUDGMENT_INSTRUCTION_POOL = [
    "If correct, answer \"Correct.\" If partially correct, answer \"Partially correct,\" then provide the more precise relation. If incorrect, answer \"Incorrect,\" then provide the correct relation.",
]

# Answer template pools (per style)
FULL_SENTENCE_ANSWER_POOL = [
    "In the image plane, {target} is {direction} {anchor}.",
]

# SINGLE_AXIS answers are constrained by instruction-following; keep as labels.
JUDGMENT_ANSWER_CORRECT_POOL = ["Correct."]
JUDGMENT_ANSWER_PARTIAL_POOL = ["Partially correct. {full_sentence}"]
JUDGMENT_ANSWER_INCORRECT_POOL = ["Incorrect. {full_sentence}"]

# Marked reference text pools
MARKED_REF_SAME_PHRASE_POOL = [
    "the object in the {color} box",
]
MARKED_REF_WITH_HINT_POOL = [
    "{name} (the object in the {color} box in the image)",
]


# ----------------------------
# Render API (called by QA logic)
# ----------------------------

def render_full_sentence_question(rng: random.Random, *, anchor: str, target: str) -> str:
    task = rng.choice(TASK_DESCRIPTION_POOL) if TASK_DESCRIPTION_POOL else ""
    q = _fmt(rng.choice(FULL_SENTENCE_QUESTION_POOL), anchor=anchor, target=target)
    ins = rng.choice(FULL_SENTENCE_INSTRUCTION_POOL) if FULL_SENTENCE_INSTRUCTION_POOL else ""
    return _join_parts([task, q, ins])


def render_full_sentence_answer(*, anchor: str, target: str, direction: str) -> str:
    # Keep answer variations fully within templates.
    tpl = FULL_SENTENCE_ANSWER_POOL[0] if FULL_SENTENCE_ANSWER_POOL else "In the image plane, {target} is {direction} {anchor}."
    return _fmt(tpl, anchor=anchor, target=target, direction=direction)


def render_single_axis_question(
    rng: random.Random,
    *,
    anchor: str,
    target: str,
    axis_name: str,
    option_a: str,
    option_b: str,
) -> str:
    task = rng.choice(TASK_DESCRIPTION_POOL) if TASK_DESCRIPTION_POOL else ""
    q = _fmt(
        rng.choice(SINGLE_AXIS_QUESTION_POOL),
        anchor=anchor,
        target=target,
        axis_name=axis_name,
        option_a=option_a,
        option_b=option_b,
    )
    ins = rng.choice(SINGLE_AXIS_INSTRUCTION_POOL) if SINGLE_AXIS_INSTRUCTION_POOL else ""
    return _join_parts([task, q, ins])


def render_single_axis_answer(*, truth: str, option_a: str, option_b: str) -> str:
    # Output is the multiple-choice label (instruction-following constraint).
    return "A" if truth == option_a else "B"


def render_judgment_statement(*, anchor: str, target: str, statement_direction: str) -> str:
    return _fmt("{target} is {statement_direction} {anchor} in the image plane.", anchor=anchor, target=target, statement_direction=statement_direction)


def render_judgment_question(rng: random.Random, *, anchor: str, target: str, statement: str) -> str:
    task = rng.choice(TASK_DESCRIPTION_POOL) if TASK_DESCRIPTION_POOL else ""
    q = _fmt(rng.choice(JUDGMENT_QUESTION_POOL), anchor=anchor, target=target, statement=statement)
    ins = rng.choice(JUDGMENT_INSTRUCTION_POOL) if JUDGMENT_INSTRUCTION_POOL else ""
    return _join_parts([task, q, ins])


def render_judgment_answer(
    *,
    mode: str,
    anchor: str,
    target: str,
    true_direction: str,
) -> str:
    full_sentence = render_full_sentence_answer(anchor=anchor, target=target, direction=true_direction)
    if mode == "correct":
        tpl = JUDGMENT_ANSWER_CORRECT_POOL[0] if JUDGMENT_ANSWER_CORRECT_POOL else "Correct."
        return _fmt(tpl, anchor=anchor, target=target, full_sentence=full_sentence)
    if mode == "partial":
        tpl = JUDGMENT_ANSWER_PARTIAL_POOL[0] if JUDGMENT_ANSWER_PARTIAL_POOL else "Partially correct. {full_sentence}"
        return _fmt(tpl, anchor=anchor, target=target, full_sentence=full_sentence)
    tpl = JUDGMENT_ANSWER_INCORRECT_POOL[0] if JUDGMENT_ANSWER_INCORRECT_POOL else "Incorrect. {full_sentence}"
    return _fmt(tpl, anchor=anchor, target=target, full_sentence=full_sentence)


def render_marked_ref_same_phrase(*, color: str) -> str:
    tpl = MARKED_REF_SAME_PHRASE_POOL[0] if MARKED_REF_SAME_PHRASE_POOL else "the object in the {color} box"
    return tpl.format(color=color)


def render_marked_ref_with_hint(*, name: str, color: str) -> str:
    tpl = MARKED_REF_WITH_HINT_POOL[0] if MARKED_REF_WITH_HINT_POOL else "{name} (the object in the {color} box in the image)"
    return tpl.format(name=name, color=color)


def render_marker_meta(roles_to_colors: Dict[str, str]) -> Tuple[list[str], dict]:
    """Shared helper: normalize meta fields for storage."""
    return list(roles_to_colors.keys()), dict(roles_to_colors)

