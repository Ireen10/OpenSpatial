from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .config.loader import (
    discover_dataset_configs,
    expand_inputs,
    load_dataset_config,
    load_global_config,
    resolve_adapter,
)
from .io.json import JsonlWriter, iter_json_file, iter_jsonl


def _checkpoint_path(output_root: Path, input_file: str) -> Path:
    # small stable filename
    import hashlib

    h = hashlib.md5(input_file.encode("utf-8")).hexdigest()  # nosec: non-crypto usage
    return output_root / ".checkpoints" / f"{h}.json"


def _read_checkpoint(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_checkpoint_atomic(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _process_jsonl_file(
    input_path: Path,
    output_path: Path,
    *,
    batch_size: int,
    resume: bool,
    strict: bool,
    output_root: Path,
) -> None:
    ckpt_path = _checkpoint_path(output_root, str(input_path))
    ckpt = _read_checkpoint(ckpt_path) if resume else None
    next_idx = int(ckpt.get("next_input_index", 0)) if ckpt else 0

    buffer: List[Dict] = []
    with JsonlWriter(output_path, append=resume and output_path.exists()) as w:
        for record, ref in iter_jsonl(input_path):
            if ref.input_index < next_idx:
                continue
            # passthrough; later replace by adapter/enrich pipeline
            out = dict(record)
            out.setdefault("aux", {})
            out["aux"]["record_ref"] = {"input_file": ref.input_file, "input_index": ref.input_index}
            buffer.append(out)
            if len(buffer) >= batch_size:
                w.write_records(buffer)
                w.flush()
                next_idx = ref.input_index + 1
                _write_checkpoint_atomic(
                    ckpt_path,
                    {"input_file": str(input_path), "next_input_index": next_idx, "errors_count": 0},
                )
                buffer.clear()
        if buffer:
            w.write_records(buffer)
            w.flush()
            next_idx = next_idx + len(buffer)
            _write_checkpoint_atomic(
                ckpt_path,
                {"input_file": str(input_path), "next_input_index": next_idx, "errors_count": 0},
            )


def _process_single_json_files(
    input_files: List[Path],
    output_dir: Path,
    *,
    batch_size: int,
    resume: bool,
    output_root: Path,
) -> None:
    out_dir = output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    part_idx = 0
    buffer: List[Dict] = []

    def flush_part() -> None:
        nonlocal part_idx, buffer
        if not buffer:
            return
        out_path = out_dir / f"part-{part_idx:06d}.jsonl"
        with JsonlWriter(out_path, append=False) as w:
            w.write_records(buffer)
            w.flush()
        buffer = []
        part_idx += 1

    for ip in input_files:
        ckpt_path = _checkpoint_path(output_root, str(ip))
        ckpt = _read_checkpoint(ckpt_path) if resume else None
        if ckpt and ckpt.get("done") is True:
            continue
        (record, ref) = next(iter_json_file(ip))
        out = dict(record)
        out.setdefault("aux", {})
        out["aux"]["record_ref"] = {"input_file": ref.input_file, "input_index": ref.input_index}
        buffer.append(out)
        _write_checkpoint_atomic(ckpt_path, {"input_file": str(ip), "done": True, "errors_count": 0})
        if len(buffer) >= batch_size:
            flush_part()
    flush_part()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="openspatial-metadata")
    p.add_argument("--config-root", required=True, help="Path to dataset config folder or a single yaml file.")
    p.add_argument("--global-config", default=None, help="Optional global.yaml with defaults.")
    p.add_argument("--output-root", default=None, help="Override output root (otherwise from global config).")
    p.add_argument("--resume", action="store_true", help="Resume from checkpoints.")
    p.add_argument("--num-workers", type=int, default=0, help="Number of workers (file-level parallel).")
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    g = load_global_config(args.global_config)
    output_root = Path(args.output_root or g.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    cfg_paths = discover_dataset_configs(args.config_root)
    for cfg_path in cfg_paths:
        ds = load_dataset_config(cfg_path)
        resolve_adapter(ds)
        for split in ds.splits:
            files = [Path(p) for p in expand_inputs(split.inputs)]
            out_dir = output_root / ds.name / split.name
            out_dir.mkdir(parents=True, exist_ok=True)

            if split.input_type == "jsonl":
                # 1:1 file mapping
                for ip in files:
                    op = out_dir / (ip.stem + ".out.jsonl")
                    _process_jsonl_file(
                        ip,
                        op,
                        batch_size=g.batch_size,
                        resume=args.resume or g.resume,
                        strict=g.strict,
                        output_root=output_root,
                    )
            elif split.input_type == "json_files":
                _process_single_json_files(
                    files,
                    out_dir,
                    batch_size=g.batch_size,
                    resume=args.resume or g.resume,
                    output_root=output_root,
                )
            else:
                raise ValueError(f"Unknown input_type: {split.input_type}")


if __name__ == "__main__":
    main()
