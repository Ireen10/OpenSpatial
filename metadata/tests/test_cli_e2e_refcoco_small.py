from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestCliE2ERefcocoSmall(unittest.TestCase):
    def test_e2e_convert_enrich_write_and_global_scale(self):
        from openspatial_metadata.cli import main

        tmp = Path(tempfile.mkdtemp(prefix="openspatial_metadata_refcoco_e2e_"))
        try:
            out_root = tmp / "out"
            global_path = tmp / "global.yaml"
            global_path.write_text(
                "metadata_output_root: placeholder\n"
                "scale: 777\n"
                "batch_size: 1\n"
                "num_workers: 0\n"
                "resume: false\n"
                "strict: true\n",
                encoding="utf-8",
            )

            cfg = (
                Path(__file__).resolve().parents[1]
                / "tests"
                / "configs"
                / "datasets"
                / "refcoco_grounding_aug_en_250618"
                / "dataset.yaml"
            )
            # CLI input glob expansion is cwd-dependent; run from repo root for stable tests.
            # __file__ = .../OpenSpatial/metadata/tests/test_cli_e2e_refcoco_small.py
            # parents[2] = .../OpenSpatial
            repo_root = Path(__file__).resolve().parents[2]
            old_cwd = Path.cwd()
            try:
                os.chdir(repo_root)
                main(
                    [
                        "--config-root",
                        str(cfg),
                        "--global-config",
                        str(global_path),
                        "--output-root",
                        str(out_root),
                    ]
                )
            finally:
                os.chdir(old_cwd)

            out_path = (
                out_root
                / "refcoco_grounding_aug_en_250618"
                / "train_small"
                / "sample_small.metadata.jsonl"
            )
            self.assertTrue(out_path.is_file(), msg=f"missing {out_path}")
            lines = out_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            rec = json.loads(lines[0])

            self.assertEqual(rec["sample"]["image"]["coord_scale"], 777)
            self.assertEqual(rec["dataset"]["source"], "refcoco")
            self.assertIn("objects", rec)
            self.assertIn("queries", rec)
            self.assertIn("relations", rec)
            self.assertIn("enrich_2d", rec.get("aux", {}))
            self.assertIn("record_ref", rec.get("aux", {}))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

