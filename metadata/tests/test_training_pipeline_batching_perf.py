from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import openspatial_metadata.cli as cli_mod
from openspatial_metadata.config.qa_tasks import QaTaskSpec
from openspatial_metadata.schema.metadata_v0 import AnnotationQaItemV0


class _Ds:
    def __init__(self, name: str) -> None:
        self.name = name
        self.meta: Dict[str, Any] = {}


class _GlobalCfg:
    def __init__(self) -> None:
        self.training_rows_per_part = 1024
        self.training_row_align = 16
        self.pipeline_streaming_enabled = True
        self.training_remainder_mode = "drop"


def _minimal_metadata_record(sample_id: str) -> Dict[str, Any]:
    return {
        "dataset": {"name": "demo", "version": "v0", "split": "train"},
        "sample": {
            "sample_id": sample_id,
            "view_id": 0,
            "image": {"path": "dummy.jpg", "coord_space": "norm_0_999", "coord_scale": 1000},
        },
        "camera": None,
        "objects": [],
        "queries": [],
        "relations": [],
        "qa_items": [],
        "aux": {},
    }


def _write_jsonl(path: Path, n: int) -> None:
    rows = [json.dumps(_minimal_metadata_record(str(i)), ensure_ascii=False) for i in range(n)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_training_pipeline_batches_checkpoint_by_batch_size(tmp_path: Path, monkeypatch) -> None:
    ip = tmp_path / "in.jsonl"
    _write_jsonl(ip, 10)

    output_root = tmp_path / "out"
    checkpoint_root = tmp_path / "ckpt"
    calls: list[dict] = []

    def _fake_ckpt(path: Path, data: Dict) -> None:
        calls.append(dict(data))

    monkeypatch.setattr(cli_mod, "_write_checkpoint_atomic", _fake_ckpt)

    registry = {"spatial_relation_2d": QaTaskSpec(name="spatial_relation_2d", type="spatial_relation_2d", params={})}
    n_done = cli_mod._process_jsonl_file_training_pipeline(
        ip,
        part_id=0,
        resume=False,
        output_root=output_root,
        checkpoint_root=checkpoint_root,
        adapter_factory=lambda: None,
        relations_2d=False,
        relations_3d=False,
        ds=_Ds("demo_ds"),
        split_name="train",
        dataset_path=str(tmp_path / "dataset.yaml"),
        qa_registry=registry,
        qa_task_name="spatial_relation_2d",
        qa_task_overrides=None,
        enable_to_metadata=False,
        enable_ensure_qa=False,
        persist_noqa=True,
        batch_size=4,
        records_parallelism=1,
        max_records=None,
        tqdm_pos=None,
        phase_timer=None,
    )

    assert n_done == 10
    # Expect flush/checkpoint on records [4, 8, 10] rather than every record.
    assert [int(c["next_input_index"]) for c in calls] == [4, 8, 10]


def test_training_pipeline_skips_noqa_dump_when_not_persisting(tmp_path: Path, monkeypatch) -> None:
    ip = tmp_path / "in.jsonl"
    _write_jsonl(ip, 3)

    output_root = tmp_path / "out"
    checkpoint_root = tmp_path / "ckpt"
    dump_calls = {"n": 0}
    orig_md_dump_timed = cli_mod._md_dump_timed

    def _counting_md_dump_timed(md, *, phase_timer=None):
        dump_calls["n"] += 1
        return orig_md_dump_timed(md, phase_timer=phase_timer)

    monkeypatch.setattr(cli_mod, "_md_dump_timed", _counting_md_dump_timed)

    registry = {"spatial_relation_2d": QaTaskSpec(name="spatial_relation_2d", type="spatial_relation_2d", params={})}
    n_done = cli_mod._process_jsonl_file_training_pipeline(
        ip,
        part_id=0,
        resume=False,
        output_root=output_root,
        checkpoint_root=checkpoint_root,
        adapter_factory=lambda: None,
        relations_2d=False,
        relations_3d=False,
        ds=_Ds("demo_ds"),
        split_name="train",
        dataset_path=str(tmp_path / "dataset.yaml"),
        qa_registry=registry,
        qa_task_name="spatial_relation_2d",
        qa_task_overrides=None,
        enable_to_metadata=False,
        enable_ensure_qa=False,
        persist_noqa=False,
        batch_size=2,
        records_parallelism=1,
        max_records=None,
        tqdm_pos=None,
        phase_timer=None,
    )

    assert n_done == 3
    # No QA items + persist_noqa=False => no payload serialization should be needed.
    assert dump_calls["n"] == 0


def test_training_pipeline_ensure_qa_avoids_extra_intermediate_dump(tmp_path: Path, monkeypatch) -> None:
    ip = tmp_path / "in.jsonl"
    _write_jsonl(ip, 2)

    output_root = tmp_path / "out"
    checkpoint_root = tmp_path / "ckpt"
    dump_calls = {"n": 0}
    orig_md_dump_timed = cli_mod._md_dump_timed

    def _counting_md_dump_timed(md, *, phase_timer=None):
        dump_calls["n"] += 1
        return orig_md_dump_timed(md, phase_timer=phase_timer)

    def _fake_build_qa_items(md, *, qa_task_name, params):
        return [
            AnnotationQaItemV0(
                qa_id="qa#0",
                task="spatial_relation_2d",
                question="q",
                answer="a",
                question_type="open_ended",
                question_tags=["2D Spatial Relation"],
                meta={},
            )
        ]

    monkeypatch.setattr(cli_mod, "_md_dump_timed", _counting_md_dump_timed)
    monkeypatch.setattr(cli_mod, "build_qa_items", _fake_build_qa_items)

    registry = {"spatial_relation_2d": QaTaskSpec(name="spatial_relation_2d", type="spatial_relation_2d", params={})}
    n_done = cli_mod._process_jsonl_file_training_pipeline(
        ip,
        part_id=0,
        resume=False,
        output_root=output_root,
        checkpoint_root=checkpoint_root,
        adapter_factory=lambda: None,
        relations_2d=False,
        relations_3d=False,
        ds=_Ds("demo_ds"),
        split_name="train",
        dataset_path=str(tmp_path / "dataset.yaml"),
        qa_registry=registry,
        qa_task_name="spatial_relation_2d",
        qa_task_overrides=None,
        enable_to_metadata=False,
        enable_ensure_qa=True,
        persist_noqa=False,
        batch_size=2,
        records_parallelism=1,
        max_records=None,
        tqdm_pos=None,
        phase_timer=None,
    )

    assert n_done == 2
    # Only final qa payload dumps are needed (one per record) after removing intermediate md dump/validate chain.
    assert dump_calls["n"] == 2


def test_training_pack_settings_default_and_pipe_override() -> None:
    g = _GlobalCfg()
    rows, align, stream, mode = cli_mod._training_pack_settings(g, pipe=None)
    assert (rows, align, stream, mode) == (1024, 16, True, "drop")

    rows2, align2, stream2, mode2 = cli_mod._training_pack_settings(
        g,
        pipe={
            "training_rows_per_part": 64,
            "training_row_align": 8,
            "pipeline_streaming_enabled": False,
            "training_remainder_mode": "drop",
        },
    )
    assert (rows2, align2, stream2, mode2) == (64, 8, False, "drop")
