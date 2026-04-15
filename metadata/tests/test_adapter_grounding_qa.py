from __future__ import annotations

import unittest

from openspatial_metadata.adapters.grounding_qa import GroundingQAAdapter


class TestGroundingQAAdapter(unittest.TestCase):
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
                                "string": "Please provide the bounding box coordinate ...",
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
                            "text": {"type": "string", "format": "utf-8", "string": "darkest hot dog"},
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


if __name__ == "__main__":
    unittest.main()

