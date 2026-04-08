
counting_questions = [
    "Find out how many [A](s) in this scene.",
    "What is the number of the [A](s)?",
    "How many [A](s) are there?",
    "Could you tell me the number of the [A](s)?",
    "Counting the number of [A](s) in this scene?",
    "How many [A](s) can you see?",
    "How many [A](s) are present?",
    "What is the count of the [A](s)?",
    "Can you provide the count of the [A]?",
    "Please count the number of [A].",
]

counting_answers = [
    "[X]",
    "There are [X] [A].",
    "The number of [A] is [X].",
    "I can see [X] [A].",
    "The count of [A] is [X].",
]

counting_questions_mcq = [
    "Find out how many [X](s) in this scene. Please consider the following options: [Y], and choose the correct one.",
    "What is the number of the [X](s)? Think about these options: [Y]. Which one do you believe is correct?",
    "How many [X](s) are there? Refer to the following options: [Y], and pick the one you think is correct.",
    "Could you tell me the number of the [X](s)? Take a moment to carefully consider the following options: [Y], and choose the correct one.",
    "How many [X](s) can you see? Here are the options to choose from: [Y]. Please select the correct answer.",
    "How many [X](s) are present? Here are the options to choose from: [Y]. Please select the correct answer.",
    "What is the count of the [X](s)? Consider the following options: [Y] and choose the correct one.",
    "Can you provide the count of the [X]? Consider the following options: [Y] and choose the correct one.",
    "Please count the number of [X]. Consider the following options: [Y] and choose the correct one.",
]

counting_answers_mcq = [
    "[X]",
    "The answer is option [X].",
    "The option [X] should be the right answer.",
]


# ─── Template Registration ───────────────────────────────────────────
from ..annotation.core.prompt_template import TemplateRegistry, PromptTemplate

TemplateRegistry.register("counting.open_ended", PromptTemplate(
    questions=counting_questions, answers=counting_answers,
))
TemplateRegistry.register("counting.mcq", PromptTemplate(
    questions=counting_questions_mcq, answers=counting_answers_mcq,
))
