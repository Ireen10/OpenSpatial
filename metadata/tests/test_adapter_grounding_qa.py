from __future__ import annotations

import json
import unittest
from pathlib import Path

from openspatial_metadata.adapters.grounding_qa import GroundingQAAdapter


class TestGroundingQAAdapter(unittest.TestCase):
    def _base_record(self):
        return {
            "meta_prompt": [""],
            "data": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "image": {
                                "type": "relative_path",
                                "format": "image/jpeg",
                                "relative_path": "type7/train2014/COCO_train2014_000000569667.jpg",
                                "width": 640,
                                "height": 426,
                            },
                        }
                    ],
                }
            ],
            "repeat_flag": 1,
            "id": "sample#0",
        }

    def _run(self, record):
        ad = GroundingQAAdapter(dataset_name="refcoco_grounding_aug_en_250618", split="train")
        return ad.convert(record)

    def test_parses_two_turn_grounding(self):
        record = {
            "meta_prompt": [""],
            "data": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "image": {
                                "type": "relative_path",
                                "format": "image/jpeg",
                                "relative_path": "type7/train2014/COCO_train2014_000000569667.jpg",
                                "width": 640,
                                "height": 426,
                            },
                        },
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "Please provide the bounding box coordinate of the region this sentence describes: yeah impossible here the one with yellow cheese on end",
                            },
                        },
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "<|object_ref_start|>yeah impossible here the one with yellow cheese on end<|object_ref_end|><|box_start|>(601,346),(953,828)<|box_end|>",
                            },
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "Please provide the bounding box coordinate of the region this sentence describes: darkest hot dog",
                            },
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "<|object_ref_start|>darkest hot dog<|object_ref_end|><|box_start|>(023,191),(353,636)<|box_end|>",
                            },
                        }
                    ],
                },
            ],
            "repeat_flag": 1,
            "id": "type7-0806-6_myNGTNg5_2690",
        }

        ad = GroundingQAAdapter(dataset_name="refcoco_grounding_aug_en_250618", split="train")
        out = ad.convert(record)

        self.assertEqual(out["sample"]["sample_id"], "type7-0806-6_myNGTNg5_2690")
        self.assertEqual(out["sample"]["image"]["path"], "type7/train2014/COCO_train2014_000000569667.jpg")
        self.assertEqual(out["sample"]["image"]["width"], 640)
        self.assertEqual(out["sample"]["image"]["height"], 426)

        self.assertEqual(len(out["queries"]), 2)
        self.assertEqual(len(out["objects"]), 2)
        self.assertEqual(out["objects"][0]["bbox_xyxy_norm_1000"], [601, 346, 953, 828])
        self.assertEqual(out["objects"][1]["bbox_xyxy_norm_1000"], [23, 191, 353, 636])

        self.assertEqual(out["queries"][0]["count"], 1)
        self.assertEqual(out["queries"][1]["count"], 1)
        self.assertTrue(out["queries"][0].get("gold_object_id"))
        self.assertTrue(out["queries"][1].get("gold_object_id"))

    def test_ref_with_multiple_boxes_emits_one_query_multiple_objects(self):
        record = self._base_record()
        record["id"] = "sample#multi_box"
        record["data"].extend(
            [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": (
                                    "<|object_ref_start|>mushroom<|object_ref_end|>"
                                    "<|box_start|>(000, 000),(111,111)<|box_end|>"
                                    "<|box_start|>(222, 222),(333,333)<|box_end|>"
                                ),
                            },
                        }
                    ],
                }
            ]
        )
        out = self._run(record)
        self.assertEqual(len(out["queries"]), 1)
        self.assertEqual(out["queries"][0]["query_text"], "mushroom")
        self.assertEqual(out["queries"][0]["count"], 2)
        self.assertIsNone(out["queries"][0].get("gold_object_id"))
        self.assertEqual(len(out["objects"]), 2)
        self.assertEqual(out["objects"][0]["bbox_xyxy_norm_1000"], [0, 0, 111, 111])
        self.assertEqual(out["objects"][1]["bbox_xyxy_norm_1000"], [222, 222, 333, 333])

    def test_stray_box_not_attached_to_previous_ref(self):
        record = self._base_record()
        record["id"] = "sample#stray_box"
        record["data"].extend(
            [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": (
                                    "<|object_ref_start|>obj1<|object_ref_end|>"
                                    "<|box_start|>(001,002),(003,004)<|box_end|>"
                                    " some text in between "
                                    "<|box_start|>(010,020),(030,040)<|box_end|>"  # stray, should be ignored
                                    "<|object_ref_start|>obj2<|object_ref_end|>"
                                    "<|box_start|>(050,060),(070,080)<|box_end|>"
                                ),
                            },
                        }
                    ],
                }
            ]
        )
        out = self._run(record)
        self.assertEqual(len(out["queries"]), 2)
        self.assertEqual(len(out["objects"]), 2)
        self.assertEqual(out["queries"][0]["query_text"], "obj1")
        self.assertEqual(out["queries"][0]["count"], 1)
        self.assertEqual(out["objects"][0]["bbox_xyxy_norm_1000"], [1, 2, 3, 4])
        self.assertEqual(out["queries"][1]["query_text"], "obj2")
        self.assertEqual(out["objects"][1]["bbox_xyxy_norm_1000"], [50, 60, 70, 80])

    def test_complex_grounded_caption_fixture(self):
        fixture = Path(__file__).resolve().parent / "fixtures" / "grounding_caption_complex.jsonl"
        record = json.loads(fixture.read_text(encoding="utf-8").strip().splitlines()[0])
        out = self._run(record)

        # Expected: 3 queries (single-box ref, two-box ref, second-turn same-box different ref),
        # 4 objects total. Stray box and ref-only segment are ignored.
        self.assertEqual(len(out["queries"]), 3)
        self.assertEqual(len(out["objects"]), 4)

        bboxes = [o["bbox_xyxy_norm_1000"] for o in out["objects"]]
        self.assertEqual(bboxes.count([10, 20, 110, 120]), 2)  # same box appears in two turns with different ref
        self.assertIn([200, 210, 260, 280], bboxes)
        self.assertIn([300, 310, 360, 380], bboxes)
        self.assertNotIn([400, 410, 450, 460], bboxes)  # stray box must not be attached

        qtexts = [q["query_text"] for q in out["queries"]]
        self.assertIn("a red backpack on the chair", qtexts)
        self.assertIn("two shiny apples on the table", qtexts)
        self.assertIn("the worn bag on the seat", qtexts)

    def test_only_ref_without_box_is_skipped(self):
        record = self._base_record()
        record["id"] = "sample#only_ref"
        record["data"].extend(
            [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "<|object_ref_start|>mushroom<|object_ref_end|>",
                            },
                        }
                    ],
                }
            ]
        )
        out = self._run(record)
        self.assertEqual(out["objects"], [])
        self.assertEqual(out["queries"], [])

    def test_only_box_without_ref_is_skipped(self):
        record = self._base_record()
        record["id"] = "sample#only_box"
        record["data"].extend(
            [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "<|box_start|>(001,002),(003,004)<|box_end|>",
                            },
                        }
                    ],
                }
            ]
        )
        out = self._run(record)
        self.assertEqual(out["objects"], [])
        self.assertEqual(out["queries"], [])

    def test_multi_turn_duplicate_ref_and_box_not_deduped(self):
        record = self._base_record()
        record["id"] = "sample#dup_ref_box"
        msg = {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": {
                        "type": "string",
                        "format": "utf-8",
                        "string": "<|object_ref_start|>hot dog<|object_ref_end|><|box_start|>(010,020),(030,040)<|box_end|>",
                    },
                }
            ],
        }
        record["data"].extend([msg, msg])
        out = self._run(record)
        self.assertEqual(len(out["queries"]), 2)
        self.assertEqual(len(out["objects"]), 2)
        self.assertEqual(out["objects"][0]["bbox_xyxy_norm_1000"], [10, 20, 30, 40])
        self.assertEqual(out["objects"][1]["bbox_xyxy_norm_1000"], [10, 20, 30, 40])
        self.assertEqual(out["queries"][0]["query_text"], "hot dog")
        self.assertEqual(out["queries"][1]["query_text"], "hot dog")

    def test_multi_turn_different_ref_same_box(self):
        record = self._base_record()
        record["id"] = "sample#diff_ref_same_box"
        record["data"].extend(
            [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "<|object_ref_start|>thing A<|object_ref_end|><|box_start|>(010,020),(030,040)<|box_end|>",
                            },
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "<|object_ref_start|>thing B<|object_ref_end|><|box_start|>(010,020),(030,040)<|box_end|>",
                            },
                        }
                    ],
                },
            ]
        )
        out = self._run(record)
        self.assertEqual(len(out["queries"]), 2)
        self.assertEqual(out["queries"][0]["query_text"], "thing A")
        self.assertEqual(out["queries"][1]["query_text"], "thing B")
        self.assertEqual(len(out["objects"]), 2)
        self.assertEqual(out["objects"][0]["bbox_xyxy_norm_1000"], [10, 20, 30, 40])
        self.assertEqual(out["objects"][1]["bbox_xyxy_norm_1000"], [10, 20, 30, 40])

    def test_multi_turn_same_ref_different_box(self):
        record = self._base_record()
        record["id"] = "sample#same_ref_diff_box"
        record["data"].extend(
            [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "<|object_ref_start|>thing<|object_ref_end|><|box_start|>(010,020),(030,040)<|box_end|>",
                            },
                        }
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": {
                                "type": "string",
                                "format": "utf-8",
                                "string": "<|object_ref_start|>thing<|object_ref_end|><|box_start|>(050,060),(070,080)<|box_end|>",
                            },
                        }
                    ],
                },
            ]
        )
        out = self._run(record)
        self.assertEqual(len(out["queries"]), 2)
        self.assertEqual(out["queries"][0]["query_text"], "thing")
        self.assertEqual(out["queries"][1]["query_text"], "thing")
        self.assertEqual(len(out["objects"]), 2)
        self.assertEqual(out["objects"][0]["bbox_xyxy_norm_1000"], [10, 20, 30, 40])
        self.assertEqual(out["objects"][1]["bbox_xyxy_norm_1000"], [50, 60, 70, 80])


if __name__ == "__main__":
    unittest.main()

