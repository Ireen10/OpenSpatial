from __future__ import annotations

import io
import json
import os
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
    SHORT_DIRECTION_ALL,
    SpatialRelation2DConfig,
    _atomic_direction_for_short_answer,
    generate_spatial_relation_2d_qa_items,
)


class TestQaSpatialRelation2D(unittest.TestCase):
    def test_atomic_short_direction_eight_way(self) -> None:
        self.assertEqual(len(SHORT_DIRECTION_ALL), 8)
        self.assertEqual(len(set(SHORT_DIRECTION_ALL)), 8)
        cases = [
            ({"components": ["left"]}, "left"),
            ({"components": ["right"]}, "right"),
            ({"components": ["above"]}, "above"),
            ({"components": ["below"]}, "below"),
            ({"components": ["left", "above"]}, "upper left"),
            ({"components": ["above", "left"]}, "upper left"),
            ({"components": ["left", "below"]}, "lower left"),
            ({"components": ["right", "above"]}, "upper right"),
            ({"components": ["right", "below"]}, "lower right"),
            ({"components": [], "predicate": "right"}, "right"),
        ]
        for rel, want in cases:
            self.assertEqual(_atomic_direction_for_short_answer(rel), want, msg=repr(rel))

    def test_generates_qa_items_without_image_bytes(self):
        md = art.build_metadata_from_grounding("grounding_caption_dense_spatial.jsonl")
        with patch.dict(os.environ, {"OPENSPATIAL_METADATA_QA_STATS": "1"}):
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

    def test_qa_stats_prints_gt_direction_histogram_to_stderr(self) -> None:
        from openspatial_metadata.qa.runtime_stats import print_and_reset_spatial_relation_2d_qa_stats

        md = art.build_metadata_from_grounding("grounding_caption_dense_spatial.jsonl")
        buf = io.StringIO()
        with patch.dict(os.environ, {"OPENSPATIAL_METADATA_QA_STATS": "1"}):
            items = generate_spatial_relation_2d_qa_items(
                md,
                cfg=SpatialRelation2DConfig(
                    random_seed=7,
                    sub_tasks={"single_axis": 1, "full_sentence": 1, "judgment": 1},
                    dual_box_keep_prob=1.0,
                ),
            )
            with patch.object(sys, "stderr", buf):
                print_and_reset_spatial_relation_2d_qa_stats(dataset="unit_ds", split="unit_split")
        self.assertGreaterEqual(len(items), 1)
        s = buf.getvalue().strip()
        self.assertTrue(s.startswith("[openspatial-metadata][qa_stats]"))
        payload = json.loads(s.split("[openspatial-metadata][qa_stats] ", 1)[1])
        self.assertEqual(payload["dataset"], "unit_ds")
        self.assertEqual(payload["split"], "unit_split")
        self.assertGreaterEqual(int(payload["n_qa_items"]), len(items))
        self.assertIsInstance(payload["top_gt_directions"], list)

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

    def test_full_sentence_without_instruction_uses_full_sentence_answer(self):
        """When instruction_mode is none, full_sentence answers should not degrade to short phrases."""
        rng = random.Random(0)
        anchor, target = "anchor A", "target B"
        forced_inst = {"none": [""]}  # only allow instruction_mode=none
        with patch.object(prompt_tpl, "FULL_SENTENCE_INSTRUCTIONS_BY_MODE", forced_inst):
            _q, ans, inst_mode, ans_mode = prompt_tpl.render_full_sentence_qa_pair_with_modes(
                rng, anchor=anchor, target=target, direction="to the left of"
            )
        self.assertEqual(inst_mode, "none")
        self.assertEqual(ans_mode, "one_sentence")
        self.assertIn("In the image plane", ans)

