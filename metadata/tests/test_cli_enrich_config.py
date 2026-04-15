from __future__ import annotations

import unittest

from openspatial_metadata.cli import _apply_enrich_if_enabled


class TestCliEnrichConfig(unittest.TestCase):
    def test_apply_enrich_disabled_is_noop(self):
        rec = {
            "dataset": {"name": "t", "version": "v0", "split": "train"},
            "sample": {"sample_id": "s/0", "view_id": 0, "image": {"path": "x.png", "coord_space": "norm_0_999", "coord_scale": 1000}},
            "objects": [
                {"object_id": "a#0", "category": "x", "bbox_xyxy_norm_1000": [0, 0, 10, 10]},
                {"object_id": "b#0", "category": "x", "bbox_xyxy_norm_1000": [100, 0, 110, 10]},
            ],
            "queries": [],
            "relations": [],
            "aux": {"record_ref": {"input_file": "f", "input_index": 0}},
        }
        out = _apply_enrich_if_enabled(rec, relations_2d=False)
        self.assertEqual(out.get("aux", {}).get("record_ref", {}).get("input_file"), "f")
        self.assertNotIn("enrich_2d", out.get("aux", {}))

    def test_apply_enrich_enabled_adds_aux_enrich_2d(self):
        rec = {
            "dataset": {"name": "t", "version": "v0", "split": "train"},
            "sample": {"sample_id": "s/0", "view_id": 0, "image": {"path": "x.png", "coord_space": "norm_0_999", "coord_scale": 1000}},
            "objects": [
                {"object_id": "a#0", "category": "x", "bbox_xyxy_norm_1000": [0, 0, 10, 10]},
                {"object_id": "b#0", "category": "x", "bbox_xyxy_norm_1000": [100, 0, 110, 10]},
            ],
            "queries": [],
            "relations": [],
            "aux": {"record_ref": {"input_file": "f", "input_index": 0}},
        }
        out = _apply_enrich_if_enabled(rec, relations_2d=True)
        self.assertIn("enrich_2d", out.get("aux", {}))
        self.assertIn("stats", out["aux"]["enrich_2d"])
        # Ensure record_ref survives enrichment deep-copy.
        self.assertEqual(out.get("aux", {}).get("record_ref", {}).get("input_file"), "f")


if __name__ == "__main__":
    unittest.main()

