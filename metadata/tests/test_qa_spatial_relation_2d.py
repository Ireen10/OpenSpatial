from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import spatial_relation_2d_artifacts as art

from openspatial_metadata.prompt_templates import spatial_relation_2d_prompt_templates as prompt_tpl
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

    def test_task_description_placeholders_are_filled_in_all_three_parts(self):
        """TASK_DESCRIPTION_POOL uses {anchor}/{target}; must not leak into final prompts."""
        forced = [
            "Answer based on the 2D image plane locations of {target} and {anchor}.",
        ]
        rng = random.Random(0)
        anchor, target = "anchor X", "target Y"
        with patch.object(prompt_tpl, "TASK_DESCRIPTION_POOL", forced):
            q_fs, _ = prompt_tpl.render_full_sentence_qa_pair(
                rng, anchor=anchor, target=target, direction="above"
            )
            q_sa, _, _, _ = prompt_tpl.render_single_axis_qa_pair_with_modes(
                rng,
                anchor=anchor,
                target=target,
                axis_name="horizontal",
                option_a="left",
                option_b="right",
                truth="left",
            )
            statement = prompt_tpl.render_judgment_statement(
                anchor=anchor, target=target, statement_direction="above"
            )
            q_j = prompt_tpl.render_judgment_question(rng, anchor=anchor, target=target, statement=statement)
        for q in (q_fs, q_sa, q_j):
            self.assertNotIn("{target}", q)
            self.assertNotIn("{anchor}", q)
            self.assertIn("target Y", q)
            self.assertIn("anchor X", q)

