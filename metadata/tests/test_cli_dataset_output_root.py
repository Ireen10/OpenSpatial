from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


class TestCliDatasetOutputRoot(unittest.TestCase):
    def test_two_datasets_write_to_two_output_roots(self):
        from openspatial_metadata.cli import main

        tmp = Path(tempfile.mkdtemp(prefix="openspatial_metadata_outroot_"))
        try:
            # Two output roots.
            out_a = tmp / "out_a"
            out_b = tmp / "out_b"

            # Global config (fallback output_root shouldn't be used here).
            g = tmp / "g.yaml"
            g.write_text(
                "metadata_output_root: fallback\nbatch_size: 2\nnum_workers: 0\nresume: false\nstrict: true\n",
                encoding="utf-8",
            )

            # Create config root with two dataset folders.
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
                        f'metadata_output_root: "{out_a.as_posix()}"',
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
                        f'metadata_output_root: "{out_b.as_posix()}"',
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

            main(["--config-root", str(cfg_root), "--global-config", str(g)])

            a_file = out_a / "dsa" / "s" / "jsonl_shard_small.metadata.jsonl"
            b_file = out_b / "dsb" / "s" / "jsonl_shard_small.metadata.jsonl"
            self.assertTrue(a_file.is_file(), msg=f"missing {a_file}")
            self.assertTrue(b_file.is_file(), msg=f"missing {b_file}")

            # sanity: they contain valid json lines
            for p in [a_file, b_file]:
                line0 = p.read_text(encoding="utf-8").splitlines()[0]
                self.assertIsInstance(json.loads(line0), dict)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

