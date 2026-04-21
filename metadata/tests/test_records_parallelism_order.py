from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional


class _Ds:
    def __init__(self, name: str) -> None:
        self.name = name
        self.meta: Dict[str, Any] = {}


class _SlowAdapter:
    def __init__(self, n_total: int) -> None:
        self._n_total = int(n_total)

    def convert(self, record: Dict) -> Dict:
        # Sleep inversely to index to force out-of-order completion under parallelism.
        sid = ((record.get("sample") or {}).get("sample_id")) if isinstance(record.get("sample"), dict) else None
        i = int(sid) if sid is not None else 0
        time.sleep(max(0.0, (self._n_total - 1 - i) * 0.01))
        out = dict(record)
        out["touched"] = True
        return out


def test_records_parallelism_preserves_order_and_checkpoint() -> None:
    from openspatial_metadata.cli import _process_jsonl_file

    tmp = Path(tempfile.mkdtemp(prefix="openspatial_meta_recpar_"))
    try:
        n = 12
        ip = tmp / "in.jsonl"
        lines = []
        for i in range(n):
            lines.append(json.dumps({"sample": {"sample_id": str(i)}}))
        ip.write_text("\n".join(lines) + "\n", encoding="utf-8")

        out_root = tmp / "out_root"
        out_dir = out_root / "d" / "s"
        out_dir.mkdir(parents=True, exist_ok=True)
        op = out_dir / "data_000000.jsonl"
        checkpoint_root = out_dir / ".checkpoints"

        def adapter_factory() -> Optional[object]:
            return _SlowAdapter(n_total=n)

        n_done = _process_jsonl_file(
            ip,
            op,
            batch_size=3,
            records_parallelism=4,
            max_records=None,
            resume=False,
            output_root=out_root,
            checkpoint_root=checkpoint_root,
            tqdm_pos=None,
            adapter_factory=adapter_factory,
            relations_2d=False,
            relations_3d=False,
            ds=_Ds("d"),
            split_name="s",
            dataset_path=str(tmp / "d.yaml"),
        )
        assert n_done == n

        # Output order must match input_index order.
        out_lines = op.read_text(encoding="utf-8").strip().splitlines()
        assert len(out_lines) == n
        idxs = []
        for ln in out_lines:
            rec = json.loads(ln)
            idxs.append(int(rec["aux"]["record_ref"]["input_index"]))
        assert idxs == list(range(n))

        # Checkpoint must reflect fully processed file.
        ckpts = sorted(checkpoint_root.glob("*.json"))
        assert len(ckpts) == 1
        ck = json.loads(ckpts[0].read_text(encoding="utf-8"))
        assert int(ck.get("next_input_index", -1)) == n
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

