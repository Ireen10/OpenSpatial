from __future__ import annotations

import unittest

from openspatial_metadata.cli import _apply_dataset_meta


class _Ds:
    def __init__(self):
        self.name = "ds"
        self.meta = {"source": "unit_test", "notes": "hello"}


class TestCliDatasetMeta(unittest.TestCase):
    def test_injects_dataset_source_and_meta(self):
        out = {"dataset": {"name": "ds", "version": "v0", "split": "s"}, "sample": {"sample_id": "x", "view_id": 0, "image": {"path": "p"}}}
        got = _apply_dataset_meta(out, ds=_Ds(), split_name="s", dataset_path="configs/ds/dataset.yaml")
        self.assertEqual(got["dataset"]["source"], "unit_test")
        self.assertEqual(got["dataset"]["dataset_path"], "configs/ds/dataset.yaml")
        self.assertEqual(got["dataset"]["meta"]["notes"], "hello")
        self.assertNotIn("source", got["dataset"]["meta"])

