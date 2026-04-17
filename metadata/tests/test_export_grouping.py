"""Tests for visual_group_key and grouping."""

from __future__ import annotations

import unittest

from openspatial_metadata.export.grouping import group_qa_items, visual_group_key
from openspatial_metadata.schema.metadata_v0 import AnnotationQaItemV0


class TestExportGrouping(unittest.TestCase):
    def test_original_key(self):
        self.assertEqual(visual_group_key({"n_marked_boxes": 0}), "original")

    def test_marked_key_stable(self):
        k = visual_group_key(
            {
                "n_marked_boxes": 2,
                "marked_roles": ["anchor", "target"],
                "mark_colors": {"anchor": "red", "target": "blue"},
            }
        )
        self.assertIn("anchor,target", k)
        self.assertIn("anchor:red", k)
        self.assertIn("target:blue", k)

    def test_group_order(self):
        items = [
            AnnotationQaItemV0(qa_id="qa#0", question="a", answer="b", meta={"n_marked_boxes": 0}),
            AnnotationQaItemV0(qa_id="qa#1", question="c", answer="d", meta={"n_marked_boxes": 0}),
            AnnotationQaItemV0(
                qa_id="qa#2",
                question="e",
                answer="f",
                meta={
                    "n_marked_boxes": 1,
                    "marked_roles": ["anchor"],
                    "mark_colors": {"anchor": "red"},
                },
            ),
        ]
        groups = group_qa_items(items)
        self.assertEqual(len(groups), 2)
        self.assertEqual(len(groups[0]), 2)
        self.assertEqual(len(groups[1]), 1)
