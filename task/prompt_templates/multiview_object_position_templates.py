position_template_questions_type1 = [
    "If the [A] is [X] of the [B] in image 1, what direction is the [C] (visible in image 2) from the [B]?",
    "If the [A] is to the [X] of the [B] in the first image, what direction is the [C] from the [B]?",
    "Given that the [A] appears [X] relative to the [B] in image 1, which direction does the [C] (seen in image 2) lie with respect to the [B]?",
    "In image 1, if the [A] is located [X] of the [B], what direction does the [C] (depicted in image 2) take from the [B]?",
    "If the [A] is positioned [X] relative to the [B] in the first image, how would you describe the direction of the [C] (visible in image 2) in relation to the [B]?",
    "What direction does the [C] (shown in image 2) occupy from the [B], given that the [A] is [X] to the [B] in image 1?"
]

position_template_answers_type1 = [
    "[T].",
    "The [C] is [T] of the [B].",
]

position_template_answers_type1_mcq = [
    "[T].",
    "[T].",
    "The answer is [T].",
]


position_template_questions_type2 = [
    "If I am at the position of the [B] in image 1, and the [A] is on the [X] side of me, what direction is the [C] (visible in image 2) from my position?",
    "Standing at the location of the [B] in the first image, with the [A] is on my [X] side, which direction does the [C] (seen in image 2 ) lie from me?",
    "From the viewpoint of the [B] in image 1, if the [A] is located at the [X] side of me, what direction does the [C] (depicted in image 2) take from my position?",
    "If I consider myself at the [B]'s position in the first image, and the [A] is positioned at the [X] side of me, how would I describe the direction of the [C] (visible in image 2) from my location?",
    "Assume I am at the [B]'s position in image 1, with the [A] on my [X] side, what direction does the [C] (shown in image 2) occupy from my viewpoint?",
    "From the perspective of the [B] in the first image, if the [A] is on the [X] side of the [B], which direction is the [C] (visible in image 2) from the [B]'s position?",
]

position_template_answers_type2 = [
    "[T].",
    "The [C] is on the [T] side.",
]

position_template_answers_type2_mcq = [
    "[T].",
    "[T].",
    "The answer is [T].",
]


# ─── Template Registration ───────────────────────────────────────────
from ..annotation.core.prompt_template import TemplateRegistry, PromptTemplate

TemplateRegistry.register("multiview_position.type1", PromptTemplate(
    questions=position_template_questions_type1,
    answers=position_template_answers_type1,
))
position_template_questions_type1_mcq = [q + "\n[O]" for q in position_template_questions_type1]
TemplateRegistry.register("multiview_position.type1_mcq", PromptTemplate(
    questions=position_template_questions_type1_mcq,
    answers=position_template_answers_type1_mcq,
))
TemplateRegistry.register("multiview_position.type2", PromptTemplate(
    questions=position_template_questions_type2,
    answers=position_template_answers_type2,
))
position_template_questions_type2_mcq = [q + "\n[O]" for q in position_template_questions_type2]
TemplateRegistry.register("multiview_position.type2_mcq", PromptTemplate(
    questions=position_template_questions_type2_mcq,
    answers=position_template_answers_type2_mcq,
))
