"""Tests for training tar ``relative_path`` naming."""

from __future__ import annotations

import unittest

from openspatial_metadata.export.grouping import visual_group_key
from openspatial_metadata.export.paths import mark_suffix_short, posix_rel_path, training_image_relpath


class TestExportPaths(unittest.TestCase):
    def test_posix_normalizes_backslashes(self):
        self.assertEqual(posix_rel_path(r"a\b\c.jpg"), "a/b/c.jpg")

    def test_original_uses_metadata_path(self):
        base = "type7/train2014/COCO_train2014_000000569667.jpg"
        rel = training_image_relpath(
            base_image_rel=base,
            meta0={"n_marked_boxes": 0},
            visual_key="original",
        )
        self.assertEqual(rel, base)

    def test_marked_adds_suffix_before_ext(self):
        base = "type7/train2014/COCO_train2014_000000569667.jpg"
        meta0 = {
            "n_marked_boxes": 2,
            "marked_roles": ["anchor", "target"],
            "mark_colors": {"anchor": "red", "target": "blue"},
        }
        vk = visual_group_key(meta0)
        short = mark_suffix_short(vk, n=8)
        rel = training_image_relpath(
            base_image_rel=base,
            meta0=meta0,
            visual_key=vk,
        )
        self.assertTrue(rel.endswith(".jpg"))
        self.assertEqual(rel, f"type7/train2014/COCO_train2014_000000569667_m{short}.jpg")
