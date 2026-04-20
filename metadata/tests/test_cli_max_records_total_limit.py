from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path


class TestCliMaxRecordsTotalLimit(unittest.TestCase):
    def test_max_records_total_counts_across_multiple_datasets(self) -> None:
        from openspatial_metadata.cli import main

        tmp = Path(tempfile.mkdtemp(prefix="openspatial_metadata_maxrec_total_"))
        try:
            out = tmp / "out"
            out.mkdir(parents=True, exist_ok=True)

            g = tmp / "g.yaml"
            g.write_text(
                "\n".join(
                    [
                        f'metadata_output_root: "{out.as_posix()}"',
                        "batch_size: 2",
                        "num_workers: 0",
                        "resume: false",
                        "strict: true",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            cfg_root = tmp / "datasets"
            (cfg_root / "dsa").mkdir(parents=True)
            (cfg_root / "dsb").mkdir(parents=True)

            fixtures = Path("metadata/tests/fixtures").resolve()
            src = fixtures / "jsonl_shard_small.jsonl"
            self.assertTrue(src.is_file(), msg=f"missing fixture {src}")

            (cfg_root / "dsa" / "dataset.yaml").write_text(
                "\n".join(
                    [
                        "name: dsa",
                        "adapter: {file_name: passthrough, class_name: PassthroughAdapter}",
                        "splits:",
                        "  - name: s",
                        "    input_type: jsonl",
                        "    inputs:",
                        f'      - "{src.as_posix()}"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (cfg_root / "dsb" / "dataset.yaml").write_text(
                "\n".join(
                    [
                        "name: dsb",
                        "adapter: {file_name: passthrough, class_name: PassthroughAdapter}",
                        "splits:",
                        "  - name: s",
                        "    input_type: jsonl",
                        "    inputs:",
                        f'      - "{src.as_posix()}"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            main(
                [
                    "--config-root",
                    str(cfg_root),
                    "--global-config",
                    str(g),
                    "--progress",
                    "none",
                    "--max-records-total",
                    "12",
                ]
            )

            p_a = out / "dsa" / "s" / "data_000000.jsonl"
            p_b = out / "dsb" / "s" / "data_000000.jsonl"
            # At least one dataset must have output; total lines across both should be exactly 12.
            n_a = len(p_a.read_text(encoding="utf-8").splitlines()) if p_a.exists() else 0
            n_b = len(p_b.read_text(encoding="utf-8").splitlines()) if p_b.exists() else 0
            self.assertEqual(n_a + n_b, 12)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

