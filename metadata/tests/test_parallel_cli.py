"""Parallel CLI tests (Plan 2026-04-15). Run from repo root: python -m pytest metadata/tests/test_parallel_cli.py -q"""
import contextlib
import json
import shutil
import tempfile
import unittest
from io import StringIO
from pathlib import Path


class TestEffectiveWorkers(unittest.TestCase):
    def test_effective_parallel_workers_matrix(self):
        from openspatial_metadata.cli import PARALLEL_WORKERS_CAP, effective_parallel_workers

        self.assertEqual(effective_parallel_workers(0, 0, 5), 0)
        self.assertEqual(effective_parallel_workers(0, 3, 5), 3)
        self.assertEqual(effective_parallel_workers(4, 1, 5), 4)
        self.assertEqual(effective_parallel_workers(10, 3, 5), 5)
        self.assertEqual(effective_parallel_workers(2, 8, 3), 2)
        self.assertEqual(effective_parallel_workers(0, 100, 5), min(5, PARALLEL_WORKERS_CAP))


class TestJsonlParallel(unittest.TestCase):
    def test_jsonl_parallel_matches_sequential_output(self):
        from openspatial_metadata.cli import main

        fixtures = Path("metadata/tests/fixtures").resolve()
        alpha = fixtures / "jsonl_shard_alpha.jsonl"
        beta = fixtures / "jsonl_shard_beta.jsonl"

        def run_case(num_workers_yaml: str, cli_workers: list) -> tuple[set, set]:
            tmp = Path(tempfile.mkdtemp(prefix="openspatial_meta_jsonl_cmp_"))
            try:
                cfg = tmp / "d.yaml"
                cfg.write_text(
                    "\n".join(
                        [
                            "name: cmp",
                            "adapter: {file_name: passthrough, class_name: PassthroughAdapter}",
                            "splits:",
                            "  - name: s",
                            "    input_type: jsonl",
                            "    inputs:",
                            f'      - "{alpha.as_posix()}"',
                            f'      - "{beta.as_posix()}"',
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
                g = tmp / "g.yaml"
                g.write_text(
                    "metadata_output_root: x\n"
                    "batch_size: 2\n"
                    f"num_workers: {num_workers_yaml}\n"
                    "resume: false\n",
                    encoding="utf-8",
                )
                out = tmp / "out"
                main(
                    ["--config-root", str(cfg), "--global-config", str(g), "--output-root", str(out)]
                    + cli_workers
                )
                sa = set()
                sb = set()
                for line in (out / "cmp" / "s" / "jsonl_shard_alpha.metadata.jsonl").read_text(encoding="utf-8").strip().splitlines():
                    sa.add(json.loads(line)["sample"]["sample_id"])
                for line in (out / "cmp" / "s" / "jsonl_shard_beta.metadata.jsonl").read_text(encoding="utf-8").strip().splitlines():
                    sb.add(json.loads(line)["sample"]["sample_id"])
                return sa, sb
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        seq_a, seq_b = run_case("0", [])
        par_a, par_b = run_case("2", [])
        self.assertEqual(seq_a, par_a)
        self.assertEqual(seq_b, par_b)
        self.assertEqual(seq_a, {"alpha/0", "alpha/1", "alpha/2"})
        self.assertEqual(seq_b, {"beta/0", "beta/1", "beta/2", "beta/3"})


class TestJsonFilesParallel(unittest.TestCase):
    def test_json_files_parallel_traceability_and_parts(self):
        from openspatial_metadata.cli import main

        src_dir = Path("metadata/tests/fixtures/json_files_small").resolve()
        tmp = Path(tempfile.mkdtemp(prefix="openspatial_meta_jf_par_"))
        try:
            jdir = tmp / "jsons"
            jdir.mkdir()
            for i in range(4):
                shutil.copy(src_dir / f"sample_{i:04d}.json", jdir / f"sample_{i:04d}.json")
            inputs_lines = "\n".join(f'      - "{(jdir / f"sample_{i:04d}.json").as_posix()}"' for i in range(4))
            cfg = tmp / "d.yaml"
            cfg.write_text(
                "\n".join(
                    [
                        "name: jfpar",
                        "adapter: {file_name: passthrough, class_name: PassthroughAdapter}",
                        "splits:",
                        "  - name: train",
                        "    input_type: json_files",
                        "    inputs:",
                        inputs_lines,
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            g = tmp / "g.yaml"
            g.write_text(
                "metadata_output_root: x\nbatch_size: 2\nnum_workers: 2\nresume: false\n",
                encoding="utf-8",
            )
            out = tmp / "out"
            main(["--config-root", str(cfg), "--global-config", str(g), "--output-root", str(out)])
            parts = sorted((out / "jfpar" / "train").glob("part-*.metadata.jsonl"))
            self.assertGreaterEqual(len(parts), 1)
            all_lines: list[str] = []
            for p in parts:
                all_lines.extend(p.read_text(encoding="utf-8").strip().splitlines())
            self.assertEqual(len(all_lines), 4)
            for line in all_lines:
                rec = json.loads(line)
                src = rec["aux"]["record_ref"]["input_file"]
                self.assertTrue(Path(src).is_file(), msg=src)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestJsonlResumeAfterParallelFailure(unittest.TestCase):
    """IT-P4: one JSONL shard completes while another fails; resume after fixing inputs."""

    def test_resume_skips_finished_shard_no_duplicate_lines(self):
        from openspatial_metadata.cli import main

        fixtures = Path("metadata/tests/fixtures").resolve()
        good_src = fixtures / "jsonl_shard_small.jsonl"
        tmp = Path(tempfile.mkdtemp(prefix="openspatial_meta_jsonl_resume_"))
        try:
            good = tmp / "good.jsonl"
            shutil.copy(good_src, good)
            bad = tmp / "bad.jsonl"
            bad.write_text("{ not json\n", encoding="utf-8")

            def write_cfg(name: str, inputs_block: str) -> Path:
                p = tmp / f"{name}.yaml"
                p.write_text(
                    "\n".join(
                        [
                            "name: jlresume",
                            "adapter: {file_name: passthrough, class_name: PassthroughAdapter}",
                            "splits:",
                            "  - name: s",
                            "    input_type: jsonl",
                            "    inputs:",
                            inputs_block,
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
                return p

            cfg_both = write_cfg(
                "d_both",
                "\n".join(
                    [
                        f'      - "{good.as_posix()}"',
                        f'      - "{bad.as_posix()}"',
                    ]
                ),
            )
            cfg_good_only = write_cfg("d_good", f'      - "{good.as_posix()}"')

            g = tmp / "g.yaml"
            g.write_text(
                "metadata_output_root: x\nbatch_size: 2\nnum_workers: 2\nresume: false\nstrict: true\n",
                encoding="utf-8",
            )
            out = tmp / "out"
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stderr(StringIO()):
                    main(
                        [
                            "--config-root",
                            str(cfg_both),
                            "--global-config",
                            str(g),
                            "--output-root",
                            str(out),
                        ]
                    )
            self.assertEqual(cm.exception.args[0], 1)

            out_good = out / "jlresume" / "s" / "good.metadata.jsonl"
            self.assertTrue(out_good.is_file())
            after_fail = out_good.read_text(encoding="utf-8").strip().splitlines()
            self.assertLessEqual(len(after_fail), 10)

            g_resume = tmp / "g_resume.yaml"
            g_resume.write_text(
                "metadata_output_root: x\nbatch_size: 2\nnum_workers: 2\nresume: true\nstrict: true\n",
                encoding="utf-8",
            )
            main(
                [
                    "--config-root",
                    str(cfg_good_only),
                    "--global-config",
                    str(g_resume),
                    "--output-root",
                    str(out),
                    "--resume",
                ]
            )
            lines_final = out_good.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines_final), 10)
            ids = {json.loads(L)["sample"]["sample_id"] for L in lines_final}
            self.assertEqual(len(ids), 10)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestStrictJsonFiles(unittest.TestCase):
    def test_bad_json_worker_exits_1_and_stderr(self):
        from openspatial_metadata.cli import main

        src_dir = Path("metadata/tests/fixtures/json_files_small").resolve()
        tmp = Path(tempfile.mkdtemp(prefix="openspatial_meta_badjson_"))
        try:
            jdir = tmp / "jsons"
            jdir.mkdir()
            shutil.copy(src_dir / "sample_0000.json", jdir / "good0.json")
            (jdir / "bad.json").write_text("{ not valid json {{{", encoding="utf-8")
            cfg = tmp / "d.yaml"
            cfg.write_text(
                "\n".join(
                    [
                        "name: badcase",
                        "adapter: {file_name: passthrough, class_name: PassthroughAdapter}",
                        "splits:",
                        "  - name: train",
                        "    input_type: json_files",
                        "    inputs:",
                        f'      - "{(jdir / "good0.json").as_posix()}"',
                        f'      - "{(jdir / "bad.json").as_posix()}"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            g = tmp / "g.yaml"
            g.write_text(
                "metadata_output_root: x\nbatch_size: 2\nnum_workers: 2\nresume: false\n",
                encoding="utf-8",
            )
            out = tmp / "out"
            bad_path = (jdir / "bad.json").resolve()
            err = StringIO()
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stderr(err):
                    main(
                        [
                            "--config-root",
                            str(cfg),
                            "--global-config",
                            str(g),
                            "--output-root",
                            str(out),
                        ]
                    )
            self.assertEqual(cm.exception.args[0], 1)
            self.assertIn(str(bad_path), err.getvalue())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
