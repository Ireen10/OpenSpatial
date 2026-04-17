from __future__ import annotations

import json
import unittest

from openspatial_metadata.schema.metadata_v0 import AnnotationQaItemV0, MetadataV0


class TestQaItemsSchema(unittest.TestCase):
    def test_metadata_without_qa_items_parses_as_empty_list(self):
        raw = {
            "dataset": {"name": "d", "version": "v0", "split": "train"},
            "sample": {
                "sample_id": "s0",
                "image": {"path": "a.jpg"},
            },
        }
        md = MetadataV0.parse_obj(raw)
        self.assertEqual(md.qa_items, [])

    def test_metadata_with_qa_items_round_trip(self):
        raw = {
            "dataset": {"name": "d", "version": "v0", "split": "train"},
            "sample": {
                "sample_id": "s0",
                "image": {"path": "a.jpg"},
            },
            "qa_items": [
                {
                    "qa_id": "qa#0",
                    "task": "spatial_relation_2d",
                    "question": "Q?",
                    "answer": "A.",
                    "question_type": "open_ended",
                    "question_tags": ["2D Spatial Relation"],
                    "meta": {"k": 1},
                    "relation_id": "relation#0",
                }
            ],
        }
        md = MetadataV0.parse_obj(raw)
        self.assertEqual(len(md.qa_items), 1)
        self.assertEqual(md.qa_items[0].qa_id, "qa#0")
        dumped = json.loads(md.json())
        self.assertEqual(len(dumped["qa_items"]), 1)

    def test_annotation_qa_item_extra_fields_allowed(self):
        item = AnnotationQaItemV0.parse_obj(
            {
                "qa_id": "qa#1",
                "question": "x",
                "answer": "y",
                "extra_note": "allowed",
            }
        )
        self.assertEqual(item.question, "x")
