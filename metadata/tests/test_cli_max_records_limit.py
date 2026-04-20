from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path


class TestCliMaxRecordsLimit(unittest.TestCase):
    def test_jsonl_split_respects_max_records_per_split(self) -> None:
        from openspatial_metadata.cli import main

        tmp = Path(tempfile.mkdtemp(prefix="openspatial_metadata_maxrec_"))
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
            (cfg_root / "ds").mkdir(parents=True)

            fixtures = Path("metadata/tests/fixtures").resolve()
            src = fixtures / "jsonl_shard_small.jsonl"
            self.assertTrue(src.is_file(), msg=f"missing fixture {src}")

            (cfg_root / "ds" / "dataset.yaml").write_text(
                "\n".join(
                    [
                        "name: ds",
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
                    "--max-records-per-split",
                    "3",
                ]
            )

            out_jsonl = out / "ds" / "s" / "data_000000.jsonl"
            self.assertTrue(out_jsonl.is_file(), msg=f"missing {out_jsonl}")
            n = len(out_jsonl.read_text(encoding="utf-8").splitlines())
            self.assertEqual(n, 3)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_jsonl_split_limit_counts_across_multiple_input_files(self) -> None:
        from openspatial_metadata.cli import main

        tmp = Path(tempfile.mkdtemp(prefix="openspatial_metadata_maxrec_2files_"))
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
            (cfg_root / "ds").mkdir(parents=True)

            fixtures = Path("metadata/tests/fixtures").resolve()
            src = fixtures / "jsonl_shard_small.jsonl"
            self.assertTrue(src.is_file(), msg=f"missing fixture {src}")
            src2 = tmp / "second.jsonl"
            src2.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

            (cfg_root / "ds" / "dataset.yaml").write_text(
                "\n".join(
                    [
                        "name: ds",
                        "adapter: {file_name: passthrough, class_name: PassthroughAdapter}",
                        "splits:",
                        "  - name: s",
                        "    input_type: jsonl",
                        "    inputs:",
                        f'      - "{src.as_posix()}"',
                        f'      - "{src2.as_posix()}"',
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
                    "--max-records-per-split",
                    "12",
                ]
            )

            p0 = out / "ds" / "s" / "data_000000.jsonl"
            p1 = out / "ds" / "s" / "data_000001.jsonl"
            self.assertTrue(p0.is_file(), msg=f"missing {p0}")
            self.assertTrue(p1.is_file(), msg=f"missing {p1}")
            n0 = len(p0.read_text(encoding="utf-8").splitlines())
            n1 = len(p1.read_text(encoding="utf-8").splitlines())
            self.assertEqual(n0 + n1, 12)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

