"""E2E: metadata + qa_items → images/data_*.tar, tarinfo, jsonl/data_*.jsonl."""

from __future__ import annotations

import json
import os
import sys
import tarfile
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import spatial_relation_2d_artifacts as art

from openspatial_metadata.export.run import (
    attach_task_result_as_qa_items,
    export_metadata_to_training_bundle,
)


class TestGroundingExportE2E(unittest.TestCase):
    def test_export_produces_tar_tarinfo_jsonl(self):
        md = art.build_metadata_from_grounding("grounding_caption_dense_spatial.jsonl")
        result, ok = art.run_task_on_metadata(
            md,
            random_seed=7,
            sub_tasks={"single_axis": 2, "full_sentence": 2, "judgment": 2},
        )
        self.assertTrue(ok)
        md_with_qa = attach_task_result_as_qa_items(md, result)

        out_env = os.environ.get("OPENSPATIAL_EXPORT_E2E_OUT", "").strip()
        if out_env:
            root = Path(out_env)
            root.mkdir(parents=True, exist_ok=True)
        else:
            import tempfile

            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            root = Path(tmp.name)

        # NOTE: When OPENSPATIAL_EXPORT_E2E_OUT is set, artifacts persist on disk for inspection.
        # When not set, the test uses a temporary directory (auto-cleaned).
        paths = export_metadata_to_training_bundle(
            md_with_qa,
            image_root=art.IMAGE_ROOT,
            output_root=root,
            part_id=0,
        )
        self.assertTrue(paths["tar"].is_file())
        self.assertTrue(paths["tarinfo"].is_file())
        self.assertTrue(paths["jsonl"].is_file())

        tarinfo = json.loads(paths["tarinfo"].read_text(encoding="utf-8"))
        self.assertIsInstance(tarinfo, dict)
        self.assertTrue(tarinfo)

        line = paths["jsonl"].read_text(encoding="utf-8").strip().splitlines()[0]
        row = json.loads(line)
        self.assertEqual(row["meta_prompt"], [""])
        self.assertEqual(row["id"], "")
        self.assertTrue(row["data"])

        rel = row["data"][0]["content"][0]["image"]["relative_path"]
        self.assertIn(rel, tarinfo)
        self.assertIn("offset_data", tarinfo[rel])
        self.assertIn("size", tarinfo[rel])
        self.assertIsNone(tarinfo[rel]["sparse"])

        with tarfile.open(paths["tar"], "r") as tar:
            names = tar.getnames()
        self.assertTrue(any(rel in n or rel == n for n in names))
