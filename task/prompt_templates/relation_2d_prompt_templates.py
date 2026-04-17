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
