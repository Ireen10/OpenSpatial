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
    "You are given an image. Answer using only what you can see about where the objects are in the picture.",
    "Consider the relative positions of {target} and {anchor} in the image provided.",
    "Answer based on the 2D image plane locations of {target} and {anchor}.",
]

# 2) Question template pools (per style)
FULL_SENTENCE_QUESTION_POOL = [
    "Determine the spatial relation between {target} and {anchor} in the image plane.",
    "Describe where {target} is located with respect to {anchor}.",
    "State the relative position of {target} with respect to {anchor}.",
    "Where is {target} located with respect to {anchor}?",
    "In which direction is {target} located relative to {anchor}?",
]

SINGLE_AXIS_QUESTION_POOL = [
    "Compare {target} and {anchor} along the {axis_name} direction. Where is {target} relative to {anchor}?\nOptions: A. {option_a} B. {option_b}",
    "Along the {axis_name} axis in the image, where is {target} with respect to {anchor}?\nOptions: A. {option_a} B. {option_b}",
    "Only considering {axis_name} position, which sentence is correct?\nA. {target} is {option_a} {anchor}.\nB. {target} is {option_b} {anchor}.",
    "In terms of {axis_name} placement in the picture, where is {target} compared with {anchor}?\nOptions: A. {option_a} B. {option_b}",
    "Looking at the {axis_name} direction only, which option best describes where {target} is relative to {anchor}?\nOptions: A. {option_a} B. {option_b}",
]

JUDGMENT_QUESTION_POOL = [
    "Judge whether this statement is correct: {statement}.",
    "Evaluate this statement: {statement}.",
    "Is this statement true based on the picture: {statement}?",
    "Decide if the following is accurate: {statement}",
    "Based on where the objects appear, is this statement right or wrong: {statement}?",
]

# 3) Instruction-following pools (per style)
# Instruction modes:
# - Keys are stable identifiers used by rendering logic.
# - Values are candidate pools for that mode.
#
# NOTE: If the selected mode is "none", we *randomly choose* an answer mode from the supported ones,
# then sample an answer template from that answer-mode pool.
FULL_SENTENCE_INSTRUCTIONS_BY_MODE: Dict[str, list[str]] = {
    # No explicit instruction appended to the prompt.
    "none": [""],
    "one_sentence": ["Answer with one complete sentence."],
    # Return only a direction phrase (no subject/object, no full sentence).
    "short_phrase": [
        "Answer shortly."
    ],
}

SINGLE_AXIS_INSTRUCTIONS_BY_MODE: Dict[str, list[str]] = {
    # No explicit instruction appended; answer mode will be chosen automatically.
    "none": [""],
    "mcq_letter": ["Respond with one letter."],
    # Optional: explicit mode asking for both letter and content.
    "mcq_letter_plus_text": ["Answer with the option letter and its text."],
}

JUDGMENT_INSTRUCTIONS_BY_MODE: Dict[str, list[str]] = {
    "with_explanation": [
        "If correct, answer \"Correct.\" If partially correct, answer \"Partially correct,\" then provide the more precise relation. If incorrect, answer \"Incorrect,\" then provide the correct relation."
    ]
}

# Answer template pools (per style)
FULL_SENTENCE_ANSWERS_BY_MODE: Dict[str, list[str]] = {
    "one_sentence": ["In the image plane, {target} is {direction} {anchor}."],
    # Short-phrase answers: keep these as phrases (no subject/object).
    "short_phrase": ["{direction}"],
}

# SINGLE_AXIS answers by mode:
# - "mcq_letter": output only "A" or "B"
# - "mcq_letter_plus_text": output like "A. left" / "B. right"
SINGLE_AXIS_ANSWERS_BY_MODE: Dict[str, list[str]] = {
    "mcq_letter": ["{letter}"],
    "mcq_letter_plus_text": ["{letter}. {text}"],
}

# Judgment answers are constrained by instruction-following; keep as labels.
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
    # Backward-compat helper: this function renders only the prompt side.
    mode = rng.choice(list(FULL_SENTENCE_INSTRUCTIONS_BY_MODE.keys()))
    ins_pool = FULL_SENTENCE_INSTRUCTIONS_BY_MODE.get(mode) or [""]
    ins = rng.choice(ins_pool)
    return _join_parts([task, q, ins])


def render_full_sentence_answer(*, anchor: str, target: str, direction: str) -> str:
    # Keep answer variations fully within templates.
    pool = FULL_SENTENCE_ANSWERS_BY_MODE.get("one_sentence") or [
        "In the image plane, {target} is {direction} {anchor}."
    ]
    tpl = random.choice(pool) if pool else "In the image plane, {target} is {direction} {anchor}."
    return _fmt(tpl, anchor=anchor, target=target, direction=direction)


def render_full_sentence_answer_by_mode(
    rng: random.Random, *, mode: str, anchor: str, target: str, direction: str
) -> str:
    pool = FULL_SENTENCE_ANSWERS_BY_MODE.get(mode) or FULL_SENTENCE_ANSWERS_BY_MODE["one_sentence"]
    tpl = rng.choice(pool) if pool else "{direction}"
    return _fmt(tpl, anchor=anchor, target=target, direction=direction)


def render_full_sentence_qa_pair(rng: random.Random, *, anchor: str, target: str, direction: str) -> Tuple[str, str]:
    """
    Render (question, answer) with explicit instruction/answer mode coupling.

    Rules:
    - Choose an instruction mode key first.
    - If mode == "none": do not append instruction; choose an answer mode key randomly, then sample that pool.
    - Else: answer mode key is the same as the instruction mode key (e.g., short_phrase -> short_phrase).
    """
    task = rng.choice(TASK_DESCRIPTION_POOL) if TASK_DESCRIPTION_POOL else ""
    q = _fmt(rng.choice(FULL_SENTENCE_QUESTION_POOL), anchor=anchor, target=target)

    inst_mode = rng.choice(list(FULL_SENTENCE_INSTRUCTIONS_BY_MODE.keys()))
    inst_pool = FULL_SENTENCE_INSTRUCTIONS_BY_MODE.get(inst_mode) or [""]
    ins = rng.choice(inst_pool)

    if inst_mode == "none":
        ans_mode = rng.choice([k for k in FULL_SENTENCE_ANSWERS_BY_MODE.keys()])
    else:
        ans_mode = inst_mode

    question = _join_parts([task, q, ins])
    answer = render_full_sentence_answer_by_mode(rng, mode=ans_mode, anchor=anchor, target=target, direction=direction)
    return question, answer


def render_full_sentence_qa_pair_with_modes(
    rng: random.Random, *, anchor: str, target: str, direction: str
) -> Tuple[str, str, str, str]:
    """
    Like `render_full_sentence_qa_pair`, but also returns (instruction_mode, answer_mode).
    """
    task = rng.choice(TASK_DESCRIPTION_POOL) if TASK_DESCRIPTION_POOL else ""
    q = _fmt(rng.choice(FULL_SENTENCE_QUESTION_POOL), anchor=anchor, target=target)

    inst_mode = rng.choice(list(FULL_SENTENCE_INSTRUCTIONS_BY_MODE.keys()))
    inst_pool = FULL_SENTENCE_INSTRUCTIONS_BY_MODE.get(inst_mode) or [""]
    ins = rng.choice(inst_pool)

    if inst_mode == "none":
        ans_mode = rng.choice([k for k in FULL_SENTENCE_ANSWERS_BY_MODE.keys()])
    else:
        ans_mode = inst_mode

    question = _join_parts([task, q, ins])
    answer = render_full_sentence_answer_by_mode(rng, mode=ans_mode, anchor=anchor, target=target, direction=direction)
    return question, answer, inst_mode, ans_mode


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
    mode = rng.choice(list(SINGLE_AXIS_INSTRUCTIONS_BY_MODE.keys()))
    ins_pool = SINGLE_AXIS_INSTRUCTIONS_BY_MODE.get(mode) or [""]
    ins = rng.choice(ins_pool)
    return _join_parts([task, q, ins])


def render_single_axis_answer_by_mode(
    rng: random.Random, *, mode: str, truth: str, option_a: str, option_b: str
) -> str:
    letter = "A" if truth == option_a else "B"
    text = option_a if letter == "A" else option_b
    pool = SINGLE_AXIS_ANSWERS_BY_MODE.get(mode) or SINGLE_AXIS_ANSWERS_BY_MODE["mcq_letter"]
    tpl = rng.choice(pool) if pool else "{letter}"
    return _fmt(tpl, letter=letter, text=text)


def render_single_axis_qa_pair_with_modes(
    rng: random.Random,
    *,
    anchor: str,
    target: str,
    axis_name: str,
    option_a: str,
    option_b: str,
    truth: str,
) -> Tuple[str, str, str, str]:
    """
    Render (question, answer, instruction_mode, answer_mode) for SINGLE_AXIS style.

    Rules:
    - Choose instruction mode key first.
    - If mode == "none": no instruction appended; choose an answer mode key randomly.
    - Else: answer mode key is the same as the instruction mode key.
    """
    task = rng.choice(TASK_DESCRIPTION_POOL) if TASK_DESCRIPTION_POOL else ""
    q = _fmt(
        rng.choice(SINGLE_AXIS_QUESTION_POOL),
        anchor=anchor,
        target=target,
        axis_name=axis_name,
        option_a=option_a,
        option_b=option_b,
    )

    inst_mode = rng.choice(list(SINGLE_AXIS_INSTRUCTIONS_BY_MODE.keys()))
    inst_pool = SINGLE_AXIS_INSTRUCTIONS_BY_MODE.get(inst_mode) or [""]
    ins = rng.choice(inst_pool)

    if inst_mode == "none":
        ans_mode = rng.choice(list(SINGLE_AXIS_ANSWERS_BY_MODE.keys()))
    else:
        ans_mode = inst_mode

    question = _join_parts([task, q, ins])
    answer = render_single_axis_answer_by_mode(
        rng, mode=ans_mode, truth=truth, option_a=option_a, option_b=option_b
    )
    return question, answer, inst_mode, ans_mode


def render_single_axis_answer(*, truth: str, option_a: str, option_b: str) -> str:
    # Backward-compat: default to letter-only.
    rng = random.Random(0)
    return render_single_axis_answer_by_mode(rng, mode="mcq_letter", truth=truth, option_a=option_a, option_b=option_b)


def render_judgment_statement(*, anchor: str, target: str, statement_direction: str) -> str:
    return _fmt("{target} is {statement_direction} {anchor} in the image plane.", anchor=anchor, target=target, statement_direction=statement_direction)


def render_judgment_question(rng: random.Random, *, anchor: str, target: str, statement: str) -> str:
    task = rng.choice(TASK_DESCRIPTION_POOL) if TASK_DESCRIPTION_POOL else ""
    q = _fmt(rng.choice(JUDGMENT_QUESTION_POOL), anchor=anchor, target=target, statement=statement)
    mode = rng.choice(list(JUDGMENT_INSTRUCTIONS_BY_MODE.keys()))
    ins_pool = JUDGMENT_INSTRUCTIONS_BY_MODE.get(mode) or [""]
    ins = rng.choice(ins_pool)
    return _join_parts([task, q, ins])


def render_judgment_answer(
    rng: random.Random,
    *,
    mode: str,
    anchor: str,
    target: str,
    true_direction: str,
) -> str:
    full_sentence = render_full_sentence_answer(anchor=anchor, target=target, direction=true_direction)
    if mode == "correct":
        tpl = rng.choice(JUDGMENT_ANSWER_CORRECT_POOL) if JUDGMENT_ANSWER_CORRECT_POOL else "Correct."
        return _fmt(tpl, anchor=anchor, target=target, full_sentence=full_sentence)
    if mode == "partial":
        tpl = (
            rng.choice(JUDGMENT_ANSWER_PARTIAL_POOL)
            if JUDGMENT_ANSWER_PARTIAL_POOL
            else "Partially correct. {full_sentence}"
        )
        return _fmt(tpl, anchor=anchor, target=target, full_sentence=full_sentence)
    tpl = (
        rng.choice(JUDGMENT_ANSWER_INCORRECT_POOL)
        if JUDGMENT_ANSWER_INCORRECT_POOL
        else "Incorrect. {full_sentence}"
    )
    return _fmt(tpl, anchor=anchor, target=target, full_sentence=full_sentence)


def render_marked_ref_same_phrase(*, color: str) -> str:
    tpl = random.choice(MARKED_REF_SAME_PHRASE_POOL) if MARKED_REF_SAME_PHRASE_POOL else "the object in the {color} box"
    return tpl.format(color=color)


def render_marked_ref_with_hint(*, name: str, color: str) -> str:
    tpl = random.choice(MARKED_REF_WITH_HINT_POOL) if MARKED_REF_WITH_HINT_POOL else "{name} (the object in the {color} box in the image)"
    return tpl.format(name=name, color=color)


def render_marker_meta(roles_to_colors: Dict[str, str]) -> Tuple[list[str], dict]:
    """Shared helper: normalize meta fields for storage."""
    return list(roles_to_colors.keys()), dict(roles_to_colors)

