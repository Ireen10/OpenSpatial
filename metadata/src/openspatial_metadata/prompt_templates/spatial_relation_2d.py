from __future__ import annotations

import random
from typing import Dict, Tuple


FULL_SENTENCE_QUESTION_TEMPLATES = [
    "Determine the 2D spatial relation between {target} and {anchor} in the image plane.",
    "Based on their locations in the image plane, describe where {target} is with respect to {anchor}.",
    "Look only at the 2D image plane and state the relative position of {target} with respect to {anchor}.",
]

SINGLE_AXIS_QUESTION_TEMPLATES = [
    "Consider the positions of {target} and {anchor} in the image plane. Where is {target} with respect to {anchor} along the {axis_name} axis? Select one option.\nOptions: A. {option_a} B. {option_b}",
    "Focus on the image-plane relation between {target} and {anchor}. Along the {axis_name} axis, choose the correct location of {target} relative to {anchor}.\nOptions: A. {option_a} B. {option_b}",
    "In the image plane, compare {target} with {anchor} only along the {axis_name} axis. Pick the correct answer.\nOptions: A. {option_a} B. {option_b}",
]

JUDGMENT_QUESTION_TEMPLATES = [
    "Consider the image-plane relation between {target} and {anchor}. Is the following statement correct: {statement}? If it is correct, answer \"Correct.\" If it is partially correct, answer \"Partially correct,\" followed by a more precise relation. If it is incorrect, answer \"Incorrect,\" followed by the correct relation.",
    "Look only at the 2D image plane. Judge whether this statement is correct: {statement}. Respond with \"Correct.\", or \"Partially correct,\" plus a more accurate description, or \"Incorrect,\" plus the correct description.",
    "Based on the image-plane positions of {target} and {anchor}, evaluate this statement: {statement}. Follow this format: \"Correct.\", or \"Partially correct,\" with a refinement, or \"Incorrect,\" with the right relation.",
]


def render_full_sentence_question(rng: random.Random, *, anchor: str, target: str) -> str:
    return rng.choice(FULL_SENTENCE_QUESTION_TEMPLATES).format(target=target, anchor=anchor)


def render_full_sentence_answer(*, anchor: str, target: str, direction: str) -> str:
    return f"In the image plane, {target} is {direction} {anchor}."


def render_single_axis_question(
    rng: random.Random,
    *,
    anchor: str,
    target: str,
    axis_name: str,
    option_a: str,
    option_b: str,
) -> str:
    return rng.choice(SINGLE_AXIS_QUESTION_TEMPLATES).format(
        target=target, anchor=anchor, axis_name=axis_name, option_a=option_a, option_b=option_b
    )


def render_single_axis_answer(*, truth: str, option_a: str, option_b: str) -> str:
    # Output is the multiple-choice label.
    return "A" if truth == option_a else "B"


def render_judgment_statement(*, anchor: str, target: str, statement_direction: str) -> str:
    return f"{target} is {statement_direction} {anchor} in the image plane."


def render_judgment_question(rng: random.Random, *, anchor: str, target: str, statement: str) -> str:
    return rng.choice(JUDGMENT_QUESTION_TEMPLATES).format(target=target, anchor=anchor, statement=statement)


def render_judgment_answer(
    *,
    mode: str,
    anchor: str,
    target: str,
    true_direction: str,
) -> str:
    if mode == "correct":
        return "Correct."
    if mode == "partial":
        return f"Partially correct. In the image plane, {target} is {true_direction} {anchor}."
    return f"Incorrect. In the image plane, {target} is {true_direction} {anchor}."


def render_marked_ref_same_phrase(*, color: str) -> str:
    return f"the object in the {color} box"


def render_marked_ref_with_hint(*, name: str, color: str) -> str:
    return f"{name} (the object in the {color} box in the image)"


def render_marker_meta(roles_to_colors: Dict[str, str]) -> Tuple[list[str], dict]:
    """Shared helper: normalize meta fields for storage."""
    return list(roles_to_colors.keys()), dict(roles_to_colors)

