"""Tests for openspatial_metadata.enrich (plan 2026-04-16_0300_metadata_next)."""
from __future__ import annotations

import unittest

from openspatial_metadata.enrich import ObjectFilterOptions, enrich_relations_2d
from openspatial_metadata.schema.metadata_v0 import DatasetV0, ImageV0, MetadataV0, ObjectV0, SampleV0


def _img(path: str = "x.png", scale: int = 1000) -> ImageV0:
    return ImageV0(path=path, coord_space="norm_0_999", coord_scale=scale)


def _meta(*objects: ObjectV0, scale: int = 1000) -> MetadataV0:
    return MetadataV0(
        dataset=DatasetV0(name="t", version="v0", split="train"),
        sample=SampleV0(sample_id="s/0", view_id=0, image=_img(scale=scale)),
        objects=list(objects),
        relations=[],
        aux={},
    )


def _box(oid: str, xyxy: list[int], cat: str = "o") -> ObjectV0:
    return ObjectV0(object_id=oid, category=cat, bbox_xyxy_norm_1000=list(xyxy))


def _pt(oid: str, uv: list[int], cat: str = "o") -> ObjectV0:
    return ObjectV0(object_id=oid, category=cat, point_uv_norm_1000=list(uv))


class TestEnrichMixedGeometry(unittest.TestCase):
    def test_both_bbox_and_point_raises(self):
        bad = ObjectV0(
            object_id="bad#0",
            category="x",
            bbox_xyxy_norm_1000=[0, 0, 10, 10],
            point_uv_norm_1000=[5, 5],
        )
        md = _meta(bad)
        with self.assertRaises(ValueError):
            enrich_relations_2d(md)


class TestEnrichGeometryPredicates(unittest.TestCase):
    def test_g1_1_target_right_of_anchor(self):
        # anchor "a#0" < "b#0" lexicographically? 'a' < 'b' — use a0, b0 style
        a = _box("a#0", [100, 100, 120, 140])
        b = _box("b#0", [400, 100, 420, 140])
        md = enrich_relations_2d(_meta(a, b))
        self.assertEqual(len(md.relations), 1)
        r = md.relations[0]
        self.assertEqual(r.anchor_id, "a#0")
        self.assertEqual(r.target_id, "b#0")
        self.assertEqual(r.predicate, "right")
        self.assertIsNone(r.components)
        self.assertEqual(r.evidence["delta_uv"], [300, 0])

    def test_g1_2_target_above_anchor(self):
        a = _box("a#0", [200, 300, 240, 360])
        b = _box("b#0", [200, 50, 240, 90])
        md = enrich_relations_2d(_meta(a, b))
        r = md.relations[0]
        self.assertEqual(r.predicate, "above")
        du, dv = r.evidence["delta_uv"]
        self.assertEqual(du, 0)
        self.assertLess(dv, 0)

    def test_g1_3_composite_right_below(self):
        a = _box("a#0", [50, 50, 80, 80])
        b = _box("b#0", [400, 200, 430, 230])
        md = enrich_relations_2d(_meta(a, b))
        r = md.relations[0]
        self.assertEqual(r.components, ["right", "below"])
        self.assertGreater(r.evidence["delta_uv"][0], 0)
        self.assertGreater(r.evidence["delta_uv"][1], 0)
        self.assertEqual(r.predicate, "right")

    def test_g1_4_horizontal_only_when_vertical_tie(self):
        a = _box("a#0", [100, 200, 150, 250])
        b = _box("b#0", [300, 205, 350, 245])
        md = enrich_relations_2d(_meta(a, b))
        r = md.relations[0]
        self.assertEqual(r.predicate, "right")
        self.assertIsNone(r.components)
        self.assertLess(abs(r.evidence["delta_uv"][1]), 12)

    def test_g1_5_near_equal_deltas_still_emits_composite(self):
        """Both axes significant and similar magnitude → composite, not dropped."""
        a = _box("a#0", [100, 100, 130, 130])
        b = _box("b#0", [300, 280, 330, 310])
        md = enrich_relations_2d(_meta(a, b))
        self.assertEqual(len(md.relations), 1)
        r = md.relations[0]
        self.assertEqual(len(r.components), 2)
        self.assertEqual(r.predicate, r.components[0])


class TestEnrichObjectFilters(unittest.TestCase):
    def test_f1_1_invalid_bbox_dropped(self):
        bad = _box("z#0", [10, 10, 10, 50])
        good = _box("a#0", [400, 100, 500, 200])
        md = enrich_relations_2d(_meta(bad, good))
        dropped = md.aux["enrich_2d"]["dropped_objects"]
        self.assertTrue(any(d["object_id"] == "z#0" for d in dropped))
        self.assertEqual(md.aux["enrich_2d"]["stats"]["n_objects_kept"], 1)

    def test_f1_2_point_out_of_bounds(self):
        p = _pt("p#0", [1500, 10])
        md = enrich_relations_2d(_meta(p))
        self.assertEqual(len(md.relations), 0)

    def test_f1_3_max_objects_cap(self):
        boxes = [_box(f"k{i}", [10 + i * 40, 10, 35 + i * 40, 200]) for i in range(5)]
        md = enrich_relations_2d(_meta(*boxes), object_filter_options=ObjectFilterOptions(max_objects_per_sample=2))
        self.assertEqual(md.aux["enrich_2d"]["stats"]["n_objects_kept"], 2)


class TestEnrichPairRules(unittest.TestCase):
    def test_r1_1_high_iou_drops(self):
        a = _box("a#0", [0, 0, 100, 100])
        b = _box("b#0", [1, 1, 99, 99])
        md = enrich_relations_2d(_meta(a, b))
        self.assertEqual(len(md.relations), 0)
        self.assertTrue(any(x["reason"] == "high_iou" for x in md.aux["enrich_2d"]["dropped_relation_candidates"]))

    def test_r1_2_near_center_drops(self):
        a = _box("a#0", [0, 0, 200, 200])
        b = _box("b#0", [90, 90, 110, 110])
        md = enrich_relations_2d(_meta(a, b))
        self.assertEqual(len(md.relations), 0)
        self.assertTrue(any(x["reason"] == "near_center" for x in md.aux["enrich_2d"]["dropped_relation_candidates"]))

    def test_r1_3_anchor_is_lexicographically_smaller_id(self):
        z = _box("z#0", [500, 100, 550, 160])
        a = _box("a#0", [100, 100, 150, 160])
        md = enrich_relations_2d(_meta(z, a))
        r = md.relations[0]
        self.assertEqual(r.anchor_id, "a#0")
        self.assertEqual(r.target_id, "z#0")


class TestEnrichPointOnly(unittest.TestCase):
    def test_two_points_relation(self):
        p1 = _pt("m#0", [100, 100])
        p2 = _pt("n#0", [400, 120])
        md = enrich_relations_2d(_meta(p1, p2))
        self.assertEqual(len(md.relations), 1)
        self.assertIn("point_uv", md.relations[0].evidence["method"])


class TestEnrichNonMutating(unittest.TestCase):
    def test_input_unchanged(self):
        a = _box("a#0", [0, 0, 50, 50])
        b = _box("b#0", [200, 0, 250, 50])
        md0 = _meta(a, b)
        md1 = enrich_relations_2d(md0)
        self.assertEqual(len(md0.relations), 0)
        self.assertGreater(len(md1.relations), 0)


class TestEnrichScaleScaling(unittest.TestCase):
    def test_coord_scale_500_smaller_min_delta(self):
        a = _box("a#0", [50, 50, 80, 80])
        b = _box("b#0", [200, 50, 230, 80])
        md = MetadataV0(
            dataset=DatasetV0(name="t", version="v0", split="train"),
            sample=SampleV0(sample_id="s", view_id=0, image=_img(scale=500)),
            objects=[a, b],
            relations=[],
            aux={},
        )
        out = enrich_relations_2d(md)
        self.assertEqual(len(out.relations), 1)


if __name__ == "__main__":
    unittest.main()
