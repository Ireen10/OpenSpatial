
point2point_correspondence_template_questions = [
    "The first image shows a point marked in [A] color. After adjusting the camera or lighting, the second image presents several [B] points labeled “A, B, C, D”. Which matches the original?",
    "In image one, a point is highlighted in [A] color. In the second image, there are multiple [B] points labeled “A, B, C, D”. Can you identify the corresponding point?",
    "The first image marks a point in [A] color. After adjusting the camera or lighting, the second image presents several [B] points labeled “A, B, C, D”. Which one matches the original?",
    "The first image shows a point highlighted in [A] color. After making adjustments to the camera or lighting, the second image reveals several [B] points labeled “A, B, C, D”. Which point matches the original?",
    "The first image features a point indicated in [A] color. Following adjustments to the camera or lighting, multiple [B] points labeled “A, B, C, D” appear in the second image. Which one matches the original?",
    "In image one, a point is indicated in [A] color. In the second image, there are several [B] points labeled “A, B, C, D”. Can you identify the corresponding point?",

]

point2point_correspondence_template_questions_num = [
    "The first image shows a point marked in [A] color. After adjusting the camera or lighting, the second image presents several [B] points labeled “1, 2, 3, 4”. Which matches the original?",
    "In image one, a point is highlighted in [A] color. In the second image, there are multiple [B] points labeled “1, 2, 3, 4”. Can you identify the corresponding point?",
    "The first image marks a point in [A] color. After adjusting the camera or lighting, the second image presents several [B] points labeled “1, 2, 3, 4”. Which one matches the original?",
    "The first image shows a point highlighted in [A] color. After making adjustments to the camera or lighting, the second image reveals several [B] points labeled “1, 2, 3, 4”. Which point matches the original?",
    "The first image features a point indicated in [A] color. Following adjustments to the camera or lighting, multiple [B] points labeled “1, 2, 3, 4” appear in the second image. Which one matches the original?",
    "In image one, a point is indicated in [A] color. In the second image, there are several [B] points labeled “1, 2, 3, 4”. Can you identify the corresponding point?",

]

point2point_correspondence_template_answers = [
    "[T].",
    "The answer is [T].",
    # "The point that matches is [T].",
    # "The correct point is [T].",
    # "The corresponding point in the second image is [T].",
    # "The point that corresponds to the original is [T].",
]


object2object_correspondence_template_questions = [
    "Does the [A] in image 1 show up in image 2?",
    "Can you find the [A] from image 1 in image 2?",
    "Is the [A] from the first image visible in the second image?",
    "Is the [A] in image 1 different from any object in image 2?"
]

positive_object2object_correspondence_template_answers = [
    "Yes.",
    "Yes, The [A] from image 1 can be found in image 2.",
    "I found the [A] in image 2.",
    "The [A] appears in image 2.",
    "The [A] is visible in image 2.",
]

negative_object2object_correspondence_template_answers = [
    "No.",
    "No, the [A] is not present in image 2.",
    "No, the [A] from image 1 cannot be found in image 2.",
    "I cannot find the [A] in image 2.",
    "The [A] is missing in image 2.",
    "The [A] does not appear in image 2.",
]


# ─── Template Registration ───────────────────────────────────────────
from ..annotation.core.prompt_template import TemplateRegistry, PromptTemplate

TemplateRegistry.register("correspondence.point2point", PromptTemplate(
    questions=point2point_correspondence_template_questions,
    answers=point2point_correspondence_template_answers,
))
TemplateRegistry.register("correspondence.point2point_num", PromptTemplate(
    questions=point2point_correspondence_template_questions_num,
    answers=point2point_correspondence_template_answers,
))
TemplateRegistry.register("correspondence.object2object", PromptTemplate(
    questions=object2object_correspondence_template_questions,
    true_answers=positive_object2object_correspondence_template_answers,
    false_answers=negative_object2object_correspondence_template_answers,
))


