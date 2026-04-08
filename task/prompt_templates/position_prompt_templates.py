height_higher_predicate_questions = [
    "Consider the real-world 3D locations of the objects. Which object has a higher location? [O]",
    "Based on the 3D positions of the objects, which one is placed at a higher elevation? [O]",
    "Looking at the real-world 3D arrangement, which object is positioned higher? [O]",
    "Considering the spatial positions of the objects in 3D space, which one sits higher? [O]",
]

height_lower_predicate_questions = [
    "Consider the real-world 3D locations of the objects. Which object has a lower location? [O]",
    "Based on the 3D positions of the objects, which one is placed at a lower elevation? [O]",
    "Looking at the real-world 3D arrangement, which object is positioned lower? [O]",
    "Considering the spatial positions of the objects in 3D space, which one sits lower? [O]",
]

next_far_questions = [
    "Consider the real-world 3D locations of the objects. Are the [A] and the [B] next to each other or far away from each other? [O]",
    "Based on the 3D spatial arrangement, are the [A] and the [B] close together or far apart? [O]",
    "Looking at the real-world positions of the objects, are the [A] and the [B] near each other or distant? [O]",
    "Considering the spatial layout, would you say the [A] and the [B] are adjacent or separated by a large distance? [O]",
]


height_answers = [
    "[X]",
]

next_far_answers = [
    "[X]",
]


# ─── Template Registration ───────────────────────────────────────────
from ..annotation.core.prompt_template import TemplateRegistry, PromptTemplate

TemplateRegistry.register("position.height_higher", PromptTemplate(
    questions=height_higher_predicate_questions, answers=height_answers,
))
TemplateRegistry.register("position.height_lower", PromptTemplate(
    questions=height_lower_predicate_questions, answers=height_answers,
))
TemplateRegistry.register("position.next_far", PromptTemplate(
    questions=next_far_questions, answers=next_far_answers,
))
