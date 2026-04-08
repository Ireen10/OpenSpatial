
#### Size Predicate Templates for single-view images ####

size_predicate_questions_single_view = [
    "What is the length of the dimension that is largest in size (length, width, or height) of the [A]? [D]",
    "What is the measurement for the longest side (length, width, or height) of the [A]? [D]",
    "Can you provide the size of the [A]'s largest dimension (length, width, or height)? [D]",
    "What is the length of the dimension that is maximum (length, width, or height) of the [A]? [D]",
    "What is the length of the dimension that is the greatest (length, width, or height) of the [A]? [D]",
    "What is the measurement of the [A]'s longest dimension (length, width, or height)? [D]",
    "Can you tell me the size of the [A]'s maximum dimension (length, width, or height)? [D]",
    "What is the length of the dimension that is the most extensive (length, width, or height) of the [A]? [D]",
    "What is the measurement of the [A]'s greatest dimension (length, width, or height)? [D]",
    "Can you provide the size of the [A]'s most significant dimension (length, width, or height)? [D]",
]

size_answers_single_view = [
    "[X]",
    "The largest dimension of the [A] is [X].",
    "The [A] measures approximately [X] at its longest side.",
]

height_predicate_questions_single_view = [
    "Could you estimate the height of the [A]? [D]",
    "What is the vertical measurement of the [A]? [D]",
    "Can you provide the height dimension of the [A]? [D]",
    "How tall does the [A] stand? [D]",
    "What is the height of the [A]? [D]",
    "Could you tell me the vertical size of the [A]? [D]",
    "What is the measurement of the [A]'s height? [D]",
    "Can you estimate how high the [A] is? [D]",
    "What is the vertical dimension of the [A]? [D]",
]

height_answers_single_view = [
    "[X]",
    "The height of the [A] is [X].",
    "The [A] stands approximately [X] tall.",
]



unit_centimeter_disclaimer = [
    "Calculations are in centimeters.",
    "Format the measurement in centimeters.",
    "Express the measurement in centimeters.",
    "All measurement are provided in centimeters.",
    "The size mentioned are in centimeters.",
    "All size references are in centimeters.",
    "Measurement are expressed in centimeters.",
    "Please be aware that the size are in centimeters.",
    "All length measurement are in centimeters.",
    "The size are indicated in centimeters.",
]

unit_meter_disclaimer = [
    "Calculations are in meters.",
    "Format the measurement in meters.",
    "Express the measurement in meters.",
    "All measurement are provided in meters.",
    "The size mentioned are in meters.",
    "Please note that the dimensions are given in meters.",
    "All size references are in meters.",
    "Measurement are expressed in meters.",
    "The dimensions provided are in meters.",
    "Please be aware that the size are in meters.",
    "All length measurement are in meters.",
    "The size are indicated in meters.",
]


#### Single-view relative size predicate templates ####

big_predicate_questions_single_view = [
    "Is the [A] bigger than the [B]?",
    "Does the [A] have a larger size compared to the [B]?",
    "Can you confirm if the [A] is bigger than the [B]?",
]

big_true_responses_single_view = [
    "Yes, the [A] is bigger than the [B].",
    "Indeed, the [A] has a larger size compared to the [B].",
    "Correct, the [A] is larger in size than the [B].",
]

big_false_responses_single_view = [
    "No, the [A] is not bigger than the [B].",
    "Actually, the [A] might be smaller or the same size as the [B].",
    "Incorrect, the [A] is not larger than the [B].",
]

small_predicate_questions_single_view = [
    "Is the [A] smaller than the [B]?",
    "Does the [A] have a smaller size compared to the [B]?",
    "Can you confirm if the [A] is smaller than the [B]?",
]

small_true_responses_single_view = [
    "Yes, the [A] is smaller than the [B].",
    "Indeed, the [A] has a smaller size compared to the [B].",
    "Correct, the [A] occupies less space than the [B].",
]

small_false_responses_single_view = [
    "No, the [A] is not smaller than the [B].",
    "Actually, the [A] might be larger or the same size as the [B].",
    "Incorrect, the [A] is not smaller in size than the [B].",
]


#### Size Predicate Templates for multi-view images ####

big_predicate_questions_multi_view = [
    "Given two different views, Is the [A] bigger than the [B]?",
    "As shown in different views, does the [A] have a larger size compared to the [B]?",
    "After reviewing the images, can you confirm if the [A] is bigger than the [B]?",
]

big_true_responses_multi_view = [
    "Yes",
    "Correct",
    "Yes, the [A] is bigger than the [B].",
    "Indeed, the [A] has a larger size compared to the [B].",
    "Correct, the [A] is larger in size than the [B].",
]

big_false_responses_multi_view = [
    "No",
    "Incorrect",
    "No, the [A] is not bigger than the [B].",
    "Actually, the [A] might be smaller or the same size as the [B].",
    "Incorrect, the [A] is not larger than the [B].",
]

small_predicate_questions_multi_view = [
    "Based on the given images, is the [A] smaller than the [B]?",
    "Considering the different perspectives of the scene, does the [A] have a smaller size compared to the [B]?",
    "After reviewing the images, can you confirm if the [A] is smaller than the [B]?",
]

small_true_responses_multi_view = [
    "Yes",
    "Correct",
    "Yes, the [A] is smaller than the [B].",
    "Indeed, the [A] has a smaller size compared to the [B].",
    "Correct, the [A] occupies less space than the [B].",
]

small_false_responses_multi_view = [
    "No",
    "Incorrect",
    "No, the [A] is not smaller than the [B].",
    "Actually, the [A] might be larger or the same size as the [B].",
    "Incorrect, the [A] is not smaller in size than the [B].",
]



size_biggest_questions = [
    "Given the multi-view images and the objects: [T], which one is the biggest?",
    "Considering the set of objects: [T] in the multi-view images, identify the one with the largest size.",
    "From the provided objects: [T] in different perspectives, which object has the greatest size?",
    "Out of the objects: [T], which one is the largest in size?",
    "From the collection of objects: [T] in different views, determine which is the biggest.",
]

size_biggest_answers = [
    "[X]",
    "The [X] is the biggest among the objects.",
    "Out of all the objects, the [X] has the largest size.",
    "In terms of size, the [X] is the biggest one.",
]

size_smallest_questions = [
    "Given the multi-view images and the objects: [T], which one is the smallest?",
    "Considering the set of objects: [T] in the multi-view images, identify the one with the smallest size.",
    "From the provided objects: [T] in different perspectives, which object has the least size?",
    "Out of the objects: [T], which one is the smallest in size?",
    "From the collection of objects: [T] in different views, determine which is the smallest.",
]

size_smallest_answers = [
    "[X]",
    "The [X] is the smallest among the objects.",
    "Out of all the objects, the [X] has the least size.",
    "In terms of size, the [X] is the smallest one.",
]


# ─── Template Registration ───────────────────────────────────────────
from ..annotation.core.prompt_template import TemplateRegistry, PromptTemplate

TemplateRegistry.register("size.absolute.single_view", PromptTemplate(
    questions=size_predicate_questions_single_view, answers=size_answers_single_view,
))
TemplateRegistry.register("size.height.single_view", PromptTemplate(
    questions=height_predicate_questions_single_view, answers=height_answers_single_view,
))
TemplateRegistry.register("size.big.single_view", PromptTemplate(
    questions=big_predicate_questions_single_view,
    true_answers=big_true_responses_single_view,
    false_answers=big_false_responses_single_view,
))
TemplateRegistry.register("size.small.single_view", PromptTemplate(
    questions=small_predicate_questions_single_view,
    true_answers=small_true_responses_single_view,
    false_answers=small_false_responses_single_view,
))
TemplateRegistry.register("size.big.multi_view", PromptTemplate(
    questions=big_predicate_questions_multi_view,
    true_answers=big_true_responses_multi_view,
    false_answers=big_false_responses_multi_view,
))
TemplateRegistry.register("size.small.multi_view", PromptTemplate(
    questions=small_predicate_questions_multi_view,
    true_answers=small_true_responses_multi_view,
    false_answers=small_false_responses_multi_view,
))
TemplateRegistry.register("size.biggest", PromptTemplate(
    questions=size_biggest_questions, answers=size_biggest_answers,
))
TemplateRegistry.register("size.smallest", PromptTemplate(
    questions=size_smallest_questions, answers=size_smallest_answers,
))
