from __future__ import annotations

import unittest

from openspatial_metadata.qa.spatial_relation_3d import SpatialRelation3DConfig, generate_spatial_relation_3d_qa_items
from openspatial_metadata.schema.metadata_v0 import DatasetV0, ImageV0, MetadataV0, ObjectV0, RelationV0, SampleV0


def _meta() -> MetadataV0:
    return MetadataV0(
        dataset=DatasetV0(name="t", version="v0", split="train"),
        sample=SampleV0(sample_id="s/0", view_id=0, image=ImageV0(path="x.png", coord_scale=1000)),
        camera=None,
        objects=[
            ObjectV0(object_id="a#0", category="chair", phrase="chair", center_xyz_cam=[0.0, 0.0, 2.0]),
            ObjectV0(object_id="b#0", category="table", phrase="table", center_xyz_cam=[1.0, -1.0, 1.0]),
        ],
        queries=[],
        relations=[
            RelationV0(
                relation_id="relation#0",
                anchor_id="a#0",
                target_id="b#0",
                predicate="front",
                ref_frame="egocentric",
                components=["front", "right", "above"],
                axis_signs={"front": 1, "right": 1, "above": 1},
                source="computed_3d",
            )
        ],
        qa_items=[],
        aux={},
    )


class TestQaSpatialRelation3D(unittest.TestCase):
    def test_generates_qa_items(self) -> None:
        md = _meta()
        cfg = SpatialRelation3DConfig(
            random_seed=11,
            sub_tasks={"atomic": 1, "composite": 1, "judgment": 1},
            judgment_true_prob=0.5,
        )
        items = generate_spatial_relation_3d_qa_items(md, cfg=cfg)
        self.assertGreaterEqual(len(items), 1)
        self.assertTrue(all(it.task == "spatial_relation_3d" for it in items))
        self.assertTrue(all(isinstance(it.meta, dict) for it in items))
        self.assertTrue(all((it.meta or {}).get("ref_frame") == "egocentric" for it in items))

    def test_short_circuit_when_no_egocentric_relations(self) -> None:
        md = _meta()
        md.relations = []
        items = generate_spatial_relation_3d_qa_items(
            md,
            cfg=SpatialRelation3DConfig(sub_tasks={"atomic": 1, "composite": 0, "judgment": 0}),
        )
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()

