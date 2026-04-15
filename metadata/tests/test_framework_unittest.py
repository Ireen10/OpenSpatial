import json
import shutil
import tempfile
import unittest
from pathlib import Path


class TestFramework(unittest.TestCase):
    def test_import_package(self):
        import openspatial_metadata  # noqa: F401

    def test_schema_roundtrip_minimal(self):
        from openspatial_metadata.schema.metadata_v0 import MetadataV0

        d = {
            "dataset": {"name": "demo", "version": "v0", "split": "train"},
            "sample": {"sample_id": "demo/0", "view_id": 0, "image": {"path": "a.png", "width": 1, "height": 1}},
            "camera": None,
            "objects": [{"object_id": "chair#0", "category": "chair"}],
            "relations": [],
            "aux": {},
        }
        m = MetadataV0.parse_obj(d)
        d2 = m.dict()
        m2 = MetadataV0.parse_obj(d2)
        self.assertEqual(m2.sample.sample_id, "demo/0")
        self.assertEqual(m2.objects[0].object_id, "chair#0")

    def test_schema_queries_backward_compatible_missing_queries(self):
        from openspatial_metadata.schema.metadata_v0 import MetadataV0

        md = MetadataV0.parse_obj(
            {
                "dataset": {"name": "t", "version": "v0", "split": "train"},
                "sample": {
                    "sample_id": "s/0",
                    "view_id": 0,
                    "image": {"path": "x.png", "coord_space": "norm_0_999", "coord_scale": 1000},
                },
                "objects": [],
                "relations": [],
                "aux": {},
            }
        )
        self.assertEqual(md.queries, [])

    def test_schema_queries_roundtrip(self):
        from openspatial_metadata.schema.metadata_v0 import MetadataV0

        raw = {
            "dataset": {"name": "t", "version": "v0", "split": "train"},
            "sample": {
                "sample_id": "s/0",
                "view_id": 0,
                "image": {"path": "x.png", "coord_space": "norm_0_999", "coord_scale": 1000},
            },
            "objects": [{"object_id": "chair#0", "category": "chair"}],
            "queries": [
                {
                    "query_id": "q0",
                    "query_text": "the chair",
                    "query_type": "single_instance_grounding",
                    "candidate_object_ids": ["chair#0"],
                    "gold_object_id": "chair#0",
                    "count": 1,
                    "filters": {"contains_spatial_terms": False},
                }
            ],
            "relations": [],
            "aux": {},
        }

        md = MetadataV0.parse_obj(raw)
        self.assertEqual(len(md.queries), 1)
        self.assertEqual(md.queries[0].query_id, "q0")
        self.assertEqual(md.queries[0].candidate_object_ids, ["chair#0"])
        self.assertEqual(md.queries[0].gold_object_id, "chair#0")
        self.assertEqual(md.queries[0].count, 1)

        out = md.dict()
        self.assertEqual(out["queries"][0]["query_id"], "q0")
        self.assertEqual(out["queries"][0]["candidate_object_ids"], ["chair#0"])
        self.assertEqual(out["queries"][0]["gold_object_id"], "chair#0")
        self.assertEqual(out["queries"][0]["count"], 1)

    def test_normalize_clamps(self):
        from openspatial_metadata.utils.normalize import pixel_to_norm_int

        w = 640
        scale = 1000
        self.assertEqual(pixel_to_norm_int(w, w, scale), scale - 1)
        self.assertEqual(pixel_to_norm_int(0, w, scale), 0)

    def test_config_loader_discovers_demo(self):
        from openspatial_metadata.config.loader import discover_dataset_configs, load_dataset_config, resolve_adapter

        paths = discover_dataset_configs(Path("metadata/configs/datasets"))
        self.assertTrue(any(p.replace("\\", "/").endswith("demo_dataset/dataset.yaml") for p in paths))

        ds = load_dataset_config("metadata/configs/datasets/demo_dataset/dataset.yaml")
        resolve_adapter(ds)
        self.assertEqual(ds.name, "demo_dataset")

    def test_cli_io(self):
        from openspatial_metadata.cli import main

        tmp = Path(tempfile.mkdtemp(prefix="openspatial_metadata_cli_test_"))
        try:
            out_root = tmp / "out"
            args = [
                "--config-root",
                "metadata/configs/datasets/demo_dataset/dataset.yaml",
                "--global-config",
                "metadata/configs/global.yaml",
                "--output-root",
                str(out_root),
            ]
            main(args)

            jsonl_out = out_root / "demo_dataset" / "train_jsonl" / "jsonl_shard_small.metadata.jsonl"
            self.assertTrue(jsonl_out.exists())
            lines = jsonl_out.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 10)
            first = json.loads(lines[0])
            self.assertIn("aux", first)
            self.assertIn("record_ref", first["aux"])

            json_out_dir = out_root / "demo_dataset" / "train_json"
            parts = sorted(json_out_dir.glob("part-*.metadata.jsonl"))
            self.assertTrue(parts)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cli_multi_jsonl_shards_separate_outputs(self):
        """
        One split may list multiple JSONL shards. With default ``num_workers: 0`` (and no
        ``--num-workers``), the split runs sequentially and writes one ``.metadata.jsonl`` per
        input (1:1 by stem), with separate checkpoints under ``output_root/.checkpoints/``.
        """
        from openspatial_metadata.cli import main

        fixtures = Path("metadata/tests/fixtures").resolve()
        alpha = fixtures / "jsonl_shard_alpha.jsonl"
        beta = fixtures / "jsonl_shard_beta.jsonl"
        self.assertTrue(alpha.is_file(), msg=f"missing fixture {alpha}")
        self.assertTrue(beta.is_file(), msg=f"missing fixture {beta}")

        tmp = Path(tempfile.mkdtemp(prefix="openspatial_metadata_multi_jsonl_"))
        try:
            cfg_path = tmp / "dataset.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        "name: multi_jsonl_fixture",
                        "meta: {source: test}",
                        "adapter:",
                        "  file_name: passthrough",
                        "  class_name: PassthroughAdapter",
                        "splits:",
                        "  - name: train_shards",
                        "    input_type: jsonl",
                        "    inputs:",
                        f'      - "{alpha.as_posix()}"',
                        f'      - "{beta.as_posix()}"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            global_path = tmp / "global.yaml"
            global_path.write_text(
                "output_root: placeholder\n"
                "batch_size: 2\n"
                "resume: false\n",
                encoding="utf-8",
            )

            out_root = tmp / "out"
            main(
                [
                    "--config-root",
                    str(cfg_path),
                    "--global-config",
                    str(global_path),
                    "--output-root",
                    str(out_root),
                ]
            )

            split_dir = out_root / "multi_jsonl_fixture" / "train_shards"
            out_a = split_dir / "jsonl_shard_alpha.metadata.jsonl"
            out_b = split_dir / "jsonl_shard_beta.metadata.jsonl"
            self.assertTrue(out_a.is_file(), msg=f"missing {out_a}")
            self.assertTrue(out_b.is_file(), msg=f"missing {out_b}")

            lines_a = out_a.read_text(encoding="utf-8").strip().splitlines()
            lines_b = out_b.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines_a), 3)
            self.assertEqual(len(lines_b), 4)
            self.assertEqual(json.loads(lines_a[0])["sample"]["sample_id"], "alpha/0")
            self.assertEqual(json.loads(lines_b[-1])["sample"]["sample_id"], "beta/3")

            ckpt_dir = out_root / ".checkpoints"
            self.assertTrue(ckpt_dir.is_dir())
            ckpts = list(ckpt_dir.glob("*.json"))
            self.assertGreaterEqual(len(ckpts), 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

