from __future__ import annotations

from openspatial_metadata.adapters.embodiedscan_3d import EmbodiedScan3DAdapter
from openspatial_metadata.adapters.omni3d import Omni3DAdapter


def test_embodiedscan_adapter_maps_objects_and_relations() -> None:
    rec = {
        "id": "scene001/frame0001",
        "image_path": "images/scene001/frame0001.jpg",
        "width": 640,
        "height": 480,
        "objects": [
            {"object_id": "1", "category": "chair", "center_xyz_cam": [0.0, 0.0, 2.0]},
            {"object_id": "2", "category": "table", "center_xyz_cam": [1.0, -1.0, 1.0]},
        ],
        "relations_3d": [
            {
                "anchor_id": "1",
                "target_id": "2",
                "predicate": "front",
                "components": ["front", "right", "above"],
                "axis_signs": {"front": 1, "right": 1, "above": 1},
            }
        ],
    }
    out = EmbodiedScan3DAdapter().convert(rec)
    assert out["sample"]["sample_id"] == "scene001/frame0001"
    assert len(out["objects"]) == 2
    assert out["relations"][0]["ref_frame"] == "egocentric"


def test_omni3d_adapter_maps_objects() -> None:
    rec = {
        "image_id": "omni_img_001",
        "file_name": "images/omni_001.jpg",
        "objects": [
            {"annotation_id": "a1", "category_name": "sofa", "center_3d": [0.2, 0.1, 3.5]},
            {"annotation_id": "a2", "category_name": "lamp", "center_3d": [-0.1, -0.2, 2.8]},
        ],
    }
    out = Omni3DAdapter().convert(rec)
    assert out["sample"]["sample_id"] == "omni_img_001"
    assert len(out["objects"]) == 2
    assert out["objects"][0]["object_id"] == "a1"
    assert out["relations"] == []

