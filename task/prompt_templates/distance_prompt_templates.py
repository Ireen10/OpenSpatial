
distance_template_questions_v2 = [
    "Measuring from the closest point of each object, what is the distance between the [A] and the [B] (in meters)?",
    "Measuring from the closest point of each object, what is the distance between the [A] and the [B] (in centimeters)?",
    "What is the distance between the [A] and the [B] (in meters)?",
    "What is the distance between the [A] and the [B] (in centimeters)?",
    "Consider the real-world 3D location of the objects. What is the distance between the [A] and the [B] (in meters)?",
    "Consider the real-world 3D location of the objects. What is the distance between the [A] and the [B] (in centimeters)?",
]

distance_template_questions_m = [q for q in distance_template_questions_v2 if "meters)" in q]
distance_template_questions_cm = [q for q in distance_template_questions_v2 if "centimeters)" in q]

distance_template_answers_v2 = [
    "[X]",
    "The distance between the [A] and the [B] is [X].",
    "The [A] and the [B] are approximately [X] apart.",
]

positional_far_choice_questions_v2 = [
    "Estimate the real-world distances between objects in this image. Which object is farther from the [C], the [A] or the [B]? [O]",
    "Based on the spatial arrangement of objects in this image, which object is more distant from the [C], the [A] or the [B]? [O]",
    "Considering the 3D positions of objects in this image, which one is farther from the [C], the [A] or the [B]? [O]",
    "From the perspective of this image, which object is more distant from the [C], the [A] or the [B]? [O]",
    "Looking at the spatial layout in this image, which object is farther from the [C], the [A] or the [B]? [O]",
    "Which of [A] and [B] is farther to [C]? [O]"
]

positional_far_choice_responses_v2 = [
    "[X].",
    "the [X] is farther from the [C].",
]


positional_close_choice_questions_v2 = [
    "Estimate the real-world distances between objects in this image. Which object is closer to the [C], the [A] or the [B]? [O]",
    "Based on the spatial arrangement of objects in this image, which object is nearer to the [C], the [A] or the [B]? [O]",
    "Considering the 3D positions of objects in this image, which one is closer to the [C], the [A] or the [B]? [O]",
    "From the perspective of this image, which object is nearer to the [C], the [A] or the [B]? [O]",
    "Looking at the spatial layout in this image, which object is closer to the [C], the [A] or the [B]? [O]",
    "Which of [A] and [B] is closer to [C]? [O]"
]

positional_close_choice_responses_v2 = [
    "[X].",
    "the [X] is closer to the [C].",
]


distance_farthest_questions = [
    "Given the multi-view images and objects: [T], which one is the farthest from the [X]?",
    "Considering the multi-view images and the set of objects [T], which object is most distant from [X]?",
    "From the provided multi-view images and objects [T], identify the object that is the farthest from [X].",
    "Among the objects [T] shown in the multi-view images, which one has the greatest distance from [X]?",
    "From the multi-view objects [T], identify the one farthest from [X].",
    "Out of the objects [T] in the multi-view images, which one is the most distant from [X]?",
    "If you view objects [T] from multiple perspectives, which one has the maximum distance to [X]?",
]

distance_farthest_answers = [
    "[X]",
    "[X] is the farthest from [Y].",
]


distance_closest_questions = [
    "Given the multi-view images and objects: [T], which one is the closest to the [X]?",
    "Considering the multi-view images and the set of objects [T], which object is nearest to [X]?",
    "From the provided multi-view images and objects [T], identify the object that is the closest to [X].",
    "Among the objects [T] shown in the multi-view images, which one has the smallest distance from [X]?",
    "From the multi-view objects [T], identify the one closest to [X].",
    "Out of the objects [T] in the multi-view images, which one is the nearest to [X]?",
    "If you view objects [T] from multiple perspectives, which one has the minimum distance to [X]?",
]

distance_closest_answers = [
    "[X]",
    "[X] is the closest to [Y].",
]


distance_obj_cam_questions = [
    "View 1 and View 2 are two different views that represent the same scene. In which view the [A] in the scene is [Y] to the spot where the camera view was positioned?",
    "Two views (View 1 and View 2) show the same scene from different angles. In which view is the [A] [Y] to the camera position?",
    "Given View 1 and View 2 of the same scene, in which view does the [A] appear [Y] to where the camera was placed?",
    "The same scene is captured in View 1 and View 2. In which view is the [A] [Y] to the camera viewpoint?",
]

distance_obj_cam_answers = [
    "[Y] to the spot where camera [X] was positioned",
    "The [A] is [Y] to the camera in [X].",
    "In [X], the [A] is [Y] to the camera position.",
]

distance_obj_cam_mcq_questions = [q + "\n[O]" for q in distance_obj_cam_questions]

distance_obj_cam_mcq_answers = [
    "[X]",
]


# ─── Template Registration ───────────────────────────────────────────
from ..annotation.core.prompt_template import TemplateRegistry, PromptTemplate

TemplateRegistry.register("distance.absolute", PromptTemplate(
    questions=distance_template_questions_v2, answers=distance_template_answers_v2,
))
TemplateRegistry.register("distance.absolute_m", PromptTemplate(
    questions=distance_template_questions_m, answers=distance_template_answers_v2,
))
TemplateRegistry.register("distance.absolute_cm", PromptTemplate(
    questions=distance_template_questions_cm, answers=distance_template_answers_v2,
))
TemplateRegistry.register("distance.relative_far", PromptTemplate(
    questions=positional_far_choice_questions_v2, answers=positional_far_choice_responses_v2,
))
TemplateRegistry.register("distance.relative_close", PromptTemplate(
    questions=positional_close_choice_questions_v2, answers=positional_close_choice_responses_v2,
))
TemplateRegistry.register("distance.farthest", PromptTemplate(
    questions=distance_farthest_questions, answers=distance_farthest_answers,
))
TemplateRegistry.register("distance.closest", PromptTemplate(
    questions=distance_closest_questions, answers=distance_closest_answers,
))
TemplateRegistry.register("distance.obj_cam", PromptTemplate(
    questions=distance_obj_cam_questions, answers=distance_obj_cam_answers,
))
TemplateRegistry.register("distance.obj_cam_mcq", PromptTemplate(
    questions=distance_obj_cam_mcq_questions, answers=distance_obj_cam_mcq_answers,
))
