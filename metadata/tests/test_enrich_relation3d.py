from __future__ import annotations

import unittest

from openspatial_metadata.enrich.relation3d import enrich_relations_3d
from openspatial_metadata.schema.metadata_v0 import DatasetV0, ImageV0, MetadataV0, ObjectV0, RelationV0, SampleV0


def _meta(*objects: ObjectV0) -> MetadataV0:
    return MetadataV0(
        dataset=DatasetV0(name="t", version="v0", split="train"),
        sample=SampleV0(sample_id="s/0", view_id=0, image=ImageV0(path="x.png", coord_scale=1000)),
        camera=None,
        objects=list(objects),
        queries=[],
        relations=[],
        qa_items=[],
        aux={},
    )


def _obj(oid: str, xyz: list[float]) -> ObjectV0:
    return ObjectV0(object_id=oid, category="o", center_xyz_cam=xyz)


class TestEnrichRelation3D(unittest.TestCase):
    def test_builds_egocentric_relation_from_center_xyz(self) -> None:
        a = _obj("a#0", [0.0, 0.0, 2.0])
        b = _obj("b#0", [1.0, -1.0, 1.0])  # right + above + front
        out = enrich_relations_3d(_meta(a, b), min_abs_delta_x=0.01, min_abs_delta_y=0.01, min_abs_delta_z=0.01)
        self.assertEqual(len(out.relations), 1)
        r = out.relations[0]
        self.assertEqual(r.ref_frame, "egocentric")
        self.assertEqual(r.source, "computed_3d")
        self.assertEqual(r.components, ["front", "right", "above"])
        self.assertIsInstance(r.axis_signs, dict)
        assert r.axis_signs is not None
        self.assertEqual(r.axis_signs.get("right"), 1)
        self.assertEqual(r.axis_signs.get("above"), 1)
        self.assertEqual(r.axis_signs.get("front"), 1)

    def test_skips_pair_without_3d_geometry(self) -> None:
        a = ObjectV0(object_id="a#0", category="o")
        b = _obj("b#0", [0.0, 0.0, 1.0])
        out = enrich_relations_3d(_meta(a, b))
        self.assertEqual(len(out.relations), 0)
        drops = out.aux.get("enrich_3d", {}).get("dropped_relation_candidates", [])
        self.assertTrue(any(d.get("reason") == "missing_3d_geometry" for d in drops))

    def test_keeps_existing_egocentric_noncomputed(self) -> None:
        a = _obj("a#0", [0.0, 0.0, 2.0])
        b = _obj("b#0", [0.5, 0.0, 1.5])
        md = _meta(a, b)
        md.relations = [
            RelationV0(
                relation_id="relation#0",
                anchor_id="a#0",
                target_id="b#0",
                predicate="front",
                ref_frame="egocentric",
                components=["front", "right"],
                source="annotated_3d",
            )
        ]
        out = enrich_relations_3d(md)
        self.assertEqual(len(out.relations), 1)
        self.assertEqual(out.relations[0].source, "annotated_3d")
        stats = out.aux.get("enrich_3d", {}).get("stats", {})
        self.assertEqual(int(stats.get("n_pairs_skipped_existing", 0)), 1)
        self.assertEqual(int(stats.get("n_conflicts_annotated_vs_geometry", 0)), 0)

    def test_reports_conflict_between_annotated_and_geometry(self) -> None:
        a = _obj("a#0", [0.0, 0.0, 2.0])
        b = _obj("b#0", [1.0, -1.0, 1.0])  # inferred: front/right/above
        md = _meta(a, b)
        md.relations = [
            RelationV0(
                relation_id="relation#0",
                anchor_id="a#0",
                target_id="b#0",
                predicate="left",
                ref_frame="egocentric",
                source="annotated_3d",
            )
        ]
        out = enrich_relations_3d(md)
        self.assertEqual(len(out.relations), 1)
        stats = out.aux.get("enrich_3d", {}).get("stats", {})
        self.assertEqual(int(stats.get("n_conflicts_annotated_vs_geometry", 0)), 1)
        conflicts = out.aux.get("enrich_3d", {}).get("conflicts_annotated_vs_geometry", [])
        self.assertTrue(conflicts)


if __name__ == "__main__":
    unittest.main()

