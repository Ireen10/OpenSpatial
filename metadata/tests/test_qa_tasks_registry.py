from __future__ import annotations

import sys
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import spatial_relation_2d_artifacts as art

from openspatial_metadata.config.qa_tasks import build_qa_items, load_qa_tasks_config, resolve_qa_task_params


class TestQaTasksRegistry(unittest.TestCase):
    def test_load_and_build_spatial_relation_2d(self):
        reg = load_qa_tasks_config("metadata/templates/configs_minimal/qa_tasks.yaml")
        params = resolve_qa_task_params(reg, qa_task_name="spatial_relation_2d", overrides={"dual_box_keep_prob": 1.0})
        md = art.build_metadata_from_grounding("grounding_caption_dense_spatial.jsonl")
        items = build_qa_items(md, qa_task_name="spatial_relation_2d", params=params)
        self.assertTrue(items)

    def test_build_spatial_relation_2d_short_circuits_when_subtasks_zero(self):
        reg = load_qa_tasks_config("metadata/templates/configs_minimal/qa_tasks.yaml")
        params = resolve_qa_task_params(
            reg,
            qa_task_name="spatial_relation_2d",
            overrides={"sub_tasks": {"single_axis": 0, "full_sentence": 0, "judgment": 0}},
        )
        md = art.build_metadata_from_grounding("grounding_caption_dense_spatial.jsonl")
        items = build_qa_items(md, qa_task_name="spatial_relation_2d", params=params)
        self.assertEqual(items, [])

