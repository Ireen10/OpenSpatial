from __future__ import annotations

import json
from pathlib import Path

import openspatial_metadata.io.json as json_io


def test_iter_jsonl_start_index_skips_json_parsing(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "x.jsonl"
    rows = [json.dumps({"i": i}, ensure_ascii=False) for i in range(6)]
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")

    loads_calls = {"n": 0}
    orig_loads = json_io.json.loads

    def _counting_loads(s: str):
        loads_calls["n"] += 1
        return orig_loads(s)

    monkeypatch.setattr(json_io.json, "loads", _counting_loads)

    out = list(json_io.iter_jsonl(p, start_index=4))
    assert [rec["i"] for rec, _ in out] == [4, 5]
    assert [ref.input_index for _, ref in out] == [4, 5]
    # Only parsed yielded rows, not skipped rows [0..3].
    assert loads_calls["n"] == 2
