object_grounding_box_template_questions = [
    "Identify the 3D bounding box surrounding the [A] within this environment.",
    "Locate the 3D bounding volume for the [A] present in the scene.",
    "Find the 3D bounding box that encapsulates the [A] in this visual representation.",
    "Extract the 3D bounding box coordinates of the [A] located in the image.",
    "Outline the 3D bounding box for the [A] visible in this setting.",
    "Pinpoint the 3D bounding box enclosing the [A] in this layout.",
    "Trace the edges of the 3D bounding box around the [A] in this scenario.",
    "Highlight the 3D bounding box that frames the [A] observed in the image.",
    "Predict the 3D location of the [A] observed in the image.",
]

object_grounding_box_template_answers = [
    "[X]",
    "The 3D bounding box for the [A] is defined by the coordinates [X].",
    "The 3D location of the [A] is defined by [X].",
]

object_grounding_box_template_questions_mcq = [
    "Identify the 3D bounding box surrounding the [X] within this environment. Consider the following options: [Y] and choose the correct one.",
    "Locate the 3D bounding volume for the [X] present in the scene. Please consider the following options: [Y], and choose the correct one.",
    "Determine the dimensions of the 3D bounding box for the [X] in this context. Think about these options: [Y]. Which one do you believe is correct?",
    "Find the 3D bounding box that encapsulates the [X] in this visual representation. Here are the options to choose from: [Y]. Please select the correct answer.",
    "Extract the 3D bounding box coordinates of the [X] located in the image. Consider these options: [Y], and choose the correct answer.",
    "Outline the 3D bounding box for the [X] visible in this setting. Before making a decision, please review the following options: [Y], and select the correct one.",
    "Calculate the 3D bounding box dimensions for the [X] depicted in the scene. Take a moment to carefully consider the following options: [Y], and choose the correct one.",
    "Pinpoint the 3D bounding box enclosing the [X] in this layout. Refer to the following options: [Y], and pick the one you think is correct.",
    "Trace the edges of the 3D bounding box around the [X] in this scenario. Refer to the following options: [Y], and pick the one you think is correct.",
    "Highlight the 3D bounding box that frames the [X] observed in the image. Please consider the following options: [Y], and choose the correct one.",
    "Predict the 3D location of the [X] observed in the image. Think about these options: [Y]. Which one do you believe is correct?",
]

object_grounding_box_template_answers_mcq = [
    "[Z]",
    "The correct 3D bounding box for the [X] is option [Z].",
    "The correct dimensions of the 3D bounding box for the [X] are given in option [Z].",
    "The correct answer is [Z]",
    "The correct 3D location of the [X] is provided in option [Z].",
]


# ─── Camera system prompt (prepended to grounding questions) ─────────

camera_system_prompt = [
    """Here are the detailed camera parameters for the image.
Camera intrinsic parameters: Horizontal fov, hfov=[H], and vertical fov, vfov=[V]. Image width=[W] and height=[I]. We do not consider distortion parameters here.
Camera coordinate: X-axis points rightward, Y-axis points downward, and Z-axis points forward. The origin point is the camera location.
We take the camera coordinate system as the world coordinate system.

3D bounding box format: [x_center, y_center, z_center, x_size, y_size, z_size, pitch, yaw, roll]
* x_center, y_center, z_center: the center of the object in the camera coordinate, in meters. z_center is the depth of the object in space.
* x_size, y_size, z_size: The dimensions of the object along the ( XYZ ) axes, in meters, when the rotation angles are zero.
* pitch, yaw, roll: Euler angles representing rotations around the X, Y, and Z axes, respectively. Euler angles are expressed in radians.
* The rotation order of Euler angles is zxy.

Output a json list where each entry contains the object name in "label" and its 3D bounding box in "bbox_3d".""",
]


# ─── Template Registration ───────────────────────────────────────────
from ..annotation.core.prompt_template import TemplateRegistry, PromptTemplate

TemplateRegistry.register("grounding_3d.open_ended", PromptTemplate(
    questions=object_grounding_box_template_questions,
    answers=object_grounding_box_template_answers,
))
TemplateRegistry.register("grounding_3d.mcq", PromptTemplate(
    questions=object_grounding_box_template_questions_mcq,
    answers=object_grounding_box_template_answers_mcq,
))
TemplateRegistry.register("grounding_3d.camera_system", PromptTemplate(
    questions=camera_system_prompt,
    answers=[""],
))