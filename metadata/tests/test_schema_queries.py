from __future__ import annotations

import unittest

from openspatial_metadata.schema.metadata_v0 import MetadataV0


class TestMetadataQueriesSchema(unittest.TestCase):
    def test_q1_backward_compatible_missing_queries(self):
        md = MetadataV0.parse_obj(
            {
                "dataset": {"name": "t", "version": "v0", "split": "train"},
                "sample": {
                    "sample_id": "s/0",
                    "view_id": 0,
                    "image": {"path": "x.png", "coord_space": "norm_0_999", "coord_scale": 1000},
                },
                "objects": [],
                "relations": [],
                "aux": {},
            }
        )
        self.assertEqual(md.queries, [])

    def test_q2_roundtrip_queries(self):
        raw = {
            "dataset": {"name": "t", "version": "v0", "split": "train"},
            "sample": {
                "sample_id": "s/0",
                "view_id": 0,
                "image": {"path": "x.png", "coord_space": "norm_0_999", "coord_scale": 1000},
            },
            "objects": [{"object_id": "chair#0", "category": "chair"}],
            "queries": [
                {
                    "query_id": "q0",
                    "query_text": "the chair",
                    "query_type": "single_instance_grounding",
                    "candidate_object_ids": ["chair#0"],
                    "gold_object_id": "chair#0",
                    "count": 1,
                    "filters": {"contains_spatial_terms": False},
                }
            ],
            "relations": [],
            "aux": {},
        }

        md = MetadataV0.parse_obj(raw)
        self.assertEqual(len(md.queries), 1)
        self.assertEqual(md.queries[0].query_id, "q0")
        self.assertEqual(md.queries[0].candidate_object_ids, ["chair#0"])
        self.assertEqual(md.queries[0].gold_object_id, "chair#0")
        self.assertEqual(md.queries[0].count, 1)

        out = md.dict()
        self.assertEqual(out["queries"][0]["query_id"], "q0")
        self.assertEqual(out["queries"][0]["candidate_object_ids"], ["chair#0"])
        self.assertEqual(out["queries"][0]["gold_object_id"], "chair#0")
        self.assertEqual(out["queries"][0]["count"], 1)


if __name__ == "__main__":
    unittest.main()

