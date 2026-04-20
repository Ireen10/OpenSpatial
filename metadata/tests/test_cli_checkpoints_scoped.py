from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from openspatial_metadata.cli import main


class TestCliCheckpointsScoped(unittest.TestCase):
    def test_checkpoint_written_under_dataset_split(self):
        tmp = Path(tempfile.mkdtemp(prefix="openspatial_metadata_ckpt_scoped_"))
        try:
            out_root = tmp / "out"
            args = [
                "--config-root",
                "metadata/tests/configs/datasets/demo_dataset/dataset.yaml",
                "--global-config",
                "metadata/templates/configs_minimal/global.yaml",
                "--output-root",
                str(out_root),
                "--resume",
            ]
            main(args)

            ckpt_dir = out_root / "demo_dataset" / "train_jsonl" / ".checkpoints"
            self.assertTrue(ckpt_dir.exists())
            self.assertTrue(any(ckpt_dir.glob("*.json")))
        finally:
            # best-effort cleanup
            pass

    def test_can_read_legacy_root_checkpoint(self):
        tmp = Path(tempfile.mkdtemp(prefix="openspatial_metadata_ckpt_legacy_"))
        out_root = tmp / "out"

        # Create legacy checkpoint only (no new-style checkpoint).
        # Demo JSONL fixture has 10 records; resume from index 5 should write 5 lines.
        input_path = str(Path("metadata/tests/fixtures/jsonl_shard_small.jsonl"))
        h = hashlib.md5(input_path.encode("utf-8")).hexdigest()
        legacy_dir = out_root / ".checkpoints"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        (legacy_dir / f"{h}.json").write_text(
            json.dumps({"input_file": input_path, "next_input_index": 5, "errors_count": 0}, ensure_ascii=False),
            encoding="utf-8",
        )

        args = [
            "--config-root",
            "metadata/tests/configs/datasets/demo_dataset/dataset.yaml",
            "--global-config",
            "metadata/templates/configs_minimal/global.yaml",
            "--output-root",
            str(out_root),
            "--resume",
        ]
        main(args)

        out_file = out_root / "demo_dataset" / "train_jsonl" / "data_000000.jsonl"
        self.assertTrue(out_file.exists())
        lines = out_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 5)

