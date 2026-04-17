from __future__ import annotations

import sys
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import spatial_relation_2d_artifacts as art

from openspatial_metadata.qa.spatial_relation_2d import (
    SpatialRelation2DConfig,
    generate_spatial_relation_2d_qa_items,
)


class TestQaSpatialRelation2D(unittest.TestCase):
    def test_generates_qa_items_without_image_bytes(self):
        md = art.build_metadata_from_grounding("grounding_caption_dense_spatial.jsonl")
        items = generate_spatial_relation_2d_qa_items(
            md,
            cfg=SpatialRelation2DConfig(
                random_seed=7,
                sub_tasks={"single_axis": 2, "full_sentence": 2, "judgment": 2},
                dual_box_keep_prob=1.0,
            ),
        )
        self.assertEqual(len(items), 6)
        self.assertTrue(all(it.question for it in items))
        self.assertTrue(all(it.answer for it in items))
        for it in items:
            self.assertIsInstance(it.meta, dict)
            self.assertIn("marked_roles", it.meta)
            self.assertIn("mark_colors", it.meta)
            self.assertIn("n_marked_boxes", it.meta)

