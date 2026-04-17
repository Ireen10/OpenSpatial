from __future__ import annotations

import sys
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import spatial_relation_2d_artifacts as art

from openspatial_metadata.enrich.filters import ObjectFilterOptions
from openspatial_metadata.enrich.relation2d import enrich_relations_2d
from openspatial_metadata.schema.metadata_v0 import MetadataV0
from task.annotation.spatial_relation_2d import AnnotationGenerator


def tearDownModule():
    art.maybe_write_artifacts_from_test()


class TestSpatialRelation2DAnnotationTask(unittest.TestCase):
    def test_dense_grounding_fixture_builds_enough_relations_end_to_end(self):
        metadata = art.build_metadata_from_grounding("grounding_caption_dense_spatial.jsonl")
        self.assertGreaterEqual(len(metadata.relations), 6)
        self.assertTrue(all(rel.relation_id for rel in metadata.relations))

    def test_task_generates_custom_outputs_without_relation_reuse(self):
        metadata = art.build_metadata_from_grounding("grounding_caption_dense_spatial.jsonl")
        result, ok = art.run_task_on_metadata(
            metadata,
            random_seed=7,
            sub_tasks={"single_axis": 2, "full_sentence": 2, "judgment": 2},
        )
        self.assertTrue(ok)
        self.assertEqual(len(result["question"]), 6)
        self.assertEqual(len(result["answer"]), 6)
        self.assertEqual(len(result["meta"]), 6)
        self.assertNotIn("QA_images", result)
        self.assertEqual(len(result["question_types"]), 6)
        self.assertEqual(len(result["question_tags"]), 6)

        relation_ids = [item["relation_id"] for item in result["meta"]]
        self.assertEqual(len(relation_ids), len(set(relation_ids)))
        self.assertTrue(all(item["qa_type"] == "2d_spatial_relation" for item in result["meta"]))
        self.assertTrue(all(item["qa_style"] in {"single_axis", "full_sentence", "judgment"} for item in result["meta"]))
        self.assertTrue(Path(result["image"]).is_file())

    def test_task_reduces_counts_when_relations_are_insufficient(self):
        metadata = art.build_metadata_from_grounding("grounding_caption_complex.jsonl")
        self.assertLess(len(metadata.relations), 6)

        result, ok = art.run_task_on_metadata(
            metadata,
            random_seed=11,
            sub_tasks={"single_axis": 2, "full_sentence": 2, "judgment": 2},
        )
        self.assertTrue(ok)
        self.assertEqual(len(result["question"]), len(metadata.relations))
        relation_ids = [item["relation_id"] for item in result["meta"]]
        self.assertEqual(len(relation_ids), len(set(relation_ids)))

    def test_same_surface_phrase_uses_split_disambiguation(self):
        md = MetadataV0.model_validate(
            {
                "dataset": {"name": "unit", "version": "v0", "split": "train"},
                "sample": {
                    "sample_id": "dup-phrase-sample",
                    "view_id": 0,
                    "image": {
                        "path": "type7/train2014/COCO_train2014_000000569667.jpg",
                        "width": 640,
                        "height": 426,
                        "coord_space": "norm_0_999",
                        "coord_scale": 1000,
                    },
                },
                "camera": None,
                "objects": [
                    {
                        "object_id": "obj#0",
                        "category": "",
                        "phrase": "two shiny apples on the table",
                        "bbox_xyxy_norm_1000": [50, 100, 220, 320],
                    },
                    {
                        "object_id": "obj#1",
                        "category": "",
                        "phrase": "two shiny apples on the table",
                        "bbox_xyxy_norm_1000": [380, 100, 550, 320],
                    },
                ],
                "queries": [],
                "relations": [],
            }
        )
        md = enrich_relations_2d(md, object_filter_options=ObjectFilterOptions(min_area_abs=0))
        self.assertEqual(len(md.relations), 1)

        task = AnnotationGenerator(
            {
                "image_root": str(art.IMAGE_ROOT),
                "random_seed": 0,
                "unique_text_only_prob": 1.0,
                "dual_box_keep_prob": 1.0,
                "sub_tasks": {"single_axis": 1, "full_sentence": 0, "judgment": 0},
            }
        )
        out, ok = task.apply_transform(md.model_dump(), idx=0)
        self.assertTrue(ok)
        q = out["question"][0]
        self.assertNotIn("Both objects share this wording", q)
        self.assertNotIn("The anchor is", q)
        self.assertIn("the object in the red box", q)
        self.assertIn("the object in the blue box", q)
        self.assertTrue(out["meta"][0].get("same_surface_description"))
        self.assertNotIn("question_lead_in", out["meta"][0])

    def test_dual_box_pairs_skipped_when_keep_prob_zero(self):
        md = MetadataV0.model_validate(
            {
                "dataset": {"name": "unit", "version": "v0", "split": "train"},
                "sample": {
                    "sample_id": "dup-phrase-skip",
                    "view_id": 0,
                    "image": {
                        "path": "type7/train2014/COCO_train2014_000000569667.jpg",
                        "width": 640,
                        "height": 426,
                        "coord_space": "norm_0_999",
                        "coord_scale": 1000,
                    },
                },
                "camera": None,
                "objects": [
                    {
                        "object_id": "obj#0",
                        "category": "",
                        "phrase": "two shiny apples on the table",
                        "bbox_xyxy_norm_1000": [50, 100, 220, 320],
                    },
                    {
                        "object_id": "obj#1",
                        "category": "",
                        "phrase": "two shiny apples on the table",
                        "bbox_xyxy_norm_1000": [380, 100, 550, 320],
                    },
                ],
                "queries": [],
                "relations": [],
            }
        )
        md = enrich_relations_2d(md, object_filter_options=ObjectFilterOptions(min_area_abs=0))
        task = AnnotationGenerator(
            {
                "image_root": str(art.IMAGE_ROOT),
                "random_seed": 0,
                "dual_box_keep_prob": 0.0,
                "sub_tasks": {"single_axis": 1, "full_sentence": 0, "judgment": 0},
            }
        )
        out, ok = task.apply_transform(md.model_dump(), idx=0)
        self.assertFalse(ok)
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
