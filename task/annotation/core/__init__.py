from .visual_marker import VisualMarker, MarkConfig, COLOR_MAP, COLOR_QUEUE_DEFAULT
from .message_builder import create_singleview_messages, create_multiview_messages

try:
    from .scene_graph import SceneGraph, ViewMeta, SceneNode, ViewAppearance
    from .base_annotation_task import BaseAnnotationTask
    from .base_multiview_task import BaseMultiviewAnnotationTask
    from utils.box_utils import (
        compute_box_3d_points,
        compute_box_3d_corners,
        compute_box_3d_corners_from_params,
        check_box_2d_overlap,
        check_box_3d_vertical_overlap,
    )
except ModuleNotFoundError:
    # Keep lightweight imports usable in environments without optional 3D deps.
    pass
