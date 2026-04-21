from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import openspatial_metadata.cli as cli_mod
from openspatial_metadata.config.qa_tasks import QaTaskSpec


class _Ds:
    def __init__(self, name: str) -> None:
        self.name = name
        self.meta: Dict[str, Any] = {}


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
    orig_md_dump = cli_mod._md_dump

    def _counting_md_dump(md):
        dump_calls["n"] += 1
        return orig_md_dump(md)

    monkeypatch.setattr(cli_mod, "_md_dump", _counting_md_dump)

    registry = {"spatial_relation_2d": QaTaskSpec(name="spatial_relation_2d", type="spatial_relation_2d", params={})}
    n_done = cli_mod._process_jsonl_file_training_pipeline(
        ip,
        part_id=0,
        resume=False,
        output_root=output_root,
        checkpoint_root=checkpoint_root,
        adapter_factory=lambda: None,
        relations_2d=False,
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
