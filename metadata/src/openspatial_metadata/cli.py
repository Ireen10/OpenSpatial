from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import import_module
from inspect import signature
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config.loader import (
    discover_dataset_configs,
    expand_inputs,
    load_dataset_config,
    load_global_config,
    resolve_adapter,
)
from .io.json import JsonlWriter, iter_json_file, iter_jsonl
from .schema.metadata_v0 import MetadataV0

PARALLEL_WORKERS_CAP = 32


def _log(msg: str) -> None:
    print(f"[openspatial-metadata] {msg}", file=sys.stderr, flush=True)


def _make_adapter_factory(
    ds: Any,
    *,
    split_name: str,
    coord_space: str,
    coord_scale: int,
) -> Callable[[], Optional[object]]:
    """
    Build a per-call adapter factory. Returns None when no adapter spec present.
    Adapter constructors may optionally accept dataset_name/split keyword args.
    """
    spec = getattr(ds, "adapter", None)
    if spec is None:
        return lambda: None

    module_name = spec.module
    class_name = spec.class_name or spec.class_
    if module_name is None and spec.file_name is not None:
        module_name = f"openspatial_metadata.adapters.{spec.file_name}"
    if module_name is None or class_name is None:
        return lambda: None

    def _factory() -> Optional[object]:
        mod = import_module(module_name)
        cls = getattr(mod, class_name)
        kwargs: Dict[str, Any] = {}
        try:
            params = signature(cls).parameters
            if "dataset_name" in params:
                kwargs["dataset_name"] = ds.name
            if "split" in params:
                kwargs["split"] = split_name
            if "coord_space" in params:
                kwargs["coord_space"] = coord_space
            if "coord_scale" in params:
                kwargs["coord_scale"] = coord_scale
            if "query_type_default" in params:
                meta = getattr(ds, "meta", None)
                if isinstance(meta, dict) and isinstance(meta.get("query_type"), str) and meta.get("query_type"):
                    kwargs["query_type_default"] = meta["query_type"]
        except Exception:
            # If signature introspection fails, fall back to minimal/no-arg init.
            kwargs = {}

        if kwargs:
            try:
                return cls(**kwargs)
            except TypeError:
                pass
        return cls()

    return _factory


def _apply_adapter(adapter: Optional[object], record: Dict) -> Dict:
    if adapter is None:
        return dict(record)
    convert = getattr(adapter, "convert", None)
    if callable(convert):
        out = convert(record)
        return dict(out) if isinstance(out, dict) else dict(record)
    return dict(record)


def _get_enrich_flags(ds: Any) -> Tuple[bool, bool]:
    enrich = getattr(ds, "enrich", None)
    if not isinstance(enrich, dict):
        return (False, False)
    return (bool(enrich.get("relations_2d", False)), bool(enrich.get("relations_3d", False)))


def _apply_enrich_if_enabled(out: Dict, *, relations_2d: bool) -> Dict:
    if not relations_2d:
        return out
    from .enrich.relation2d import enrich_relations_2d

    md = MetadataV0.parse_obj(out)
    md2 = enrich_relations_2d(md)
    return md2.dict()


def _apply_dataset_meta(out: Dict, *, ds: Any, split_name: str, dataset_path: Optional[str] = None) -> Dict:
    """
    Inject dataset config meta into output metadata.
    - Fills missing dataset.name/version/split
    - Fills missing dataset.source from ds.meta.source
    - Stores ds.meta under dataset.meta (extra field) when not already present
    """
    if not isinstance(out, dict):
        return dict(out)

    d = out.get("dataset")
    if not isinstance(d, dict):
        d = {}
        out["dataset"] = d

    d.setdefault("name", getattr(ds, "name", "unknown"))
    d.setdefault("version", "v0")
    d.setdefault("split", split_name)
    if isinstance(dataset_path, str) and dataset_path:
        d.setdefault("dataset_path", dataset_path)

    meta = getattr(ds, "meta", None)
    if isinstance(meta, dict):
        if d.get("source") in (None, "") and isinstance(meta.get("source"), str) and meta.get("source"):
            d["source"] = meta["source"]
        if "meta" not in d:
            reserved = {"name", "version", "split", "source", "dataset_path", "meta"}
            filtered = {k: v for k, v in meta.items() if k not in reserved and k not in d}
            if filtered:
                d["meta"] = filtered

    return out


def effective_parallel_workers(cli_n: int, global_n: int, file_count: int, cap: int = PARALLEL_WORKERS_CAP) -> int:
    """
    Plan §num_workers: effective = cli_n if cli_n > 0 else global_n; then min(effective, F, cap).
    Values <= 1 mean no thread pool (sequential).
    """
    if file_count <= 0:
        return 0
    raw = cli_n if cli_n > 0 else global_n
    raw = max(0, raw)
    return min(raw, file_count, cap)


def _checkpoint_path(output_root: Path, input_file: str) -> Path:
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
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
) -> None:
    del strict  # reserved for future per-record error policy
    ckpt_path = _checkpoint_path(output_root, str(input_path))
    ckpt = _read_checkpoint(ckpt_path) if resume else None
    next_idx = int(ckpt.get("next_input_index", 0)) if ckpt else 0

    buffer: List[Dict] = []
    adapter = adapter_factory()
    with JsonlWriter(output_path, append=resume and output_path.exists()) as w:
        for record, ref in iter_jsonl(input_path):
            if ref.input_index < next_idx:
                continue
            out = _apply_adapter(adapter, record)
            out.setdefault("aux", {})
            out["aux"]["record_ref"] = {"input_file": ref.input_file, "input_index": ref.input_index}
            out = _apply_dataset_meta(out, ds=ds, split_name=split_name, dataset_path=dataset_path)
            out = _apply_enrich_if_enabled(out, relations_2d=relations_2d)
            buffer.append(out)
            if len(buffer) >= batch_size:
                w.write_records(buffer)
                w.flush()
                next_idx = ref.input_index + 1
                _log(f"{ds.name}/{split_name}: {input_path.name} processed={next_idx}")
                _write_checkpoint_atomic(
                    ckpt_path,
                    {"input_file": str(input_path), "next_input_index": next_idx, "errors_count": 0},
                )
                buffer.clear()
        if buffer:
            w.write_records(buffer)
            w.flush()
            next_idx = next_idx + len(buffer)
            _log(f"{ds.name}/{split_name}: {input_path.name} processed={next_idx}")
            _write_checkpoint_atomic(
                ckpt_path,
                {"input_file": str(input_path), "next_input_index": next_idx, "errors_count": 0},
            )


def _process_jsonl_files_parallel(
    files: List[Path],
    out_dir: Path,
    *,
    effective: int,
    batch_size: int,
    resume: bool,
    strict: bool,
    output_root: Path,
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ex = ThreadPoolExecutor(max_workers=effective)
    futures = {}
    try:
        for ip in files:
            op = out_dir / (ip.stem + ".metadata.jsonl")
            fut = ex.submit(
                _process_jsonl_file,
                ip,
                op,
                batch_size=batch_size,
                resume=resume,
                strict=strict,
                output_root=output_root,
                adapter_factory=adapter_factory,
                relations_2d=relations_2d,
                ds=ds,
                split_name=split_name,
                dataset_path=dataset_path,
            )
            futures[fut] = ip
        for fut in as_completed(futures):
            ip = futures[fut]
            try:
                fut.result()
                _log(f"{ds.name}/{split_name}: done {ip.name}")
            except Exception as exc:  # noqa: BLE001 — surface to user under strict
                print(f"[openspatial-metadata] JSONL worker failed: {ip}\n{exc!r}", file=sys.stderr)
                ex.shutdown(wait=True, cancel_futures=True)
                sys.exit(1)
    finally:
        ex.shutdown(wait=True, cancel_futures=False)


def _read_single_json_file_record(
    ip: Path,
    *,
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
) -> Dict:
    (record, ref) = next(iter_json_file(ip))
    adapter = adapter_factory()
    out = _apply_adapter(adapter, record)
    out.setdefault("aux", {})
    out["aux"]["record_ref"] = {"input_file": ref.input_file, "input_index": ref.input_index}
    out = _apply_dataset_meta(out, ds=ds, split_name=split_name, dataset_path=dataset_path)
    out = _apply_enrich_if_enabled(out, relations_2d=relations_2d)
    return out


def _flush_json_files_buffer_with_checkpoints(
    buffer: List[Dict],
    out_dir: Path,
    part_idx: int,
    output_root: Path,
) -> int:
    """Write one part-*.jsonl and mark done checkpoint for each record's source file."""
    if not buffer:
        return part_idx
    out_path = out_dir / f"part-{part_idx:06d}.metadata.jsonl"
    with JsonlWriter(out_path, append=False) as w:
        w.write_records(buffer)
        w.flush()
    for rec in buffer:
        src = rec.get("aux", {}).get("record_ref", {}).get("input_file")
        if src:
            _write_checkpoint_atomic(
                _checkpoint_path(output_root, str(src)),
                {"input_file": str(src), "done": True, "errors_count": 0},
            )
    return part_idx + 1


def _process_json_files_sequential(
    input_files: List[Path],
    out_dir: Path,
    *,
    batch_size: int,
    resume: bool,
    output_root: Path,
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    part_idx = 0
    buffer: List[Dict] = []
    for ip in input_files:
        ckpt_path = _checkpoint_path(output_root, str(ip))
        ckpt = _read_checkpoint(ckpt_path) if resume else None
        if ckpt and ckpt.get("done") is True:
            continue
        rec = _read_single_json_file_record(
            ip,
            adapter_factory=adapter_factory,
            relations_2d=relations_2d,
            ds=ds,
            split_name=split_name,
            dataset_path=dataset_path,
        )
        buffer.append(rec)
        if len(buffer) >= batch_size:
            part_idx = _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, output_root)
            buffer.clear()
    if buffer:
        _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, output_root)


def _process_json_files_parallel(
    input_files: List[Path],
    out_dir: Path,
    *,
    effective: int,
    batch_size: int,
    resume: bool,
    output_root: Path,
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pending: List[Path] = []
    for ip in input_files:
        ckpt_path = _checkpoint_path(output_root, str(ip))
        ckpt = _read_checkpoint(ckpt_path) if resume else None
        if ckpt and ckpt.get("done") is True:
            continue
        pending.append(ip)
    if not pending:
        return

    part_idx = 0
    buffer: List[Dict] = []
    ex = ThreadPoolExecutor(max_workers=effective)
    futures = {}
    try:
        for ip in pending:
            futures[
                ex.submit(
                    _read_single_json_file_record,
                    ip,
                    adapter_factory=adapter_factory,
                    relations_2d=relations_2d,
                    ds=ds,
                    split_name=split_name,
                    dataset_path=dataset_path,
                )
            ] = ip
        for fut in as_completed(futures):
            ip = futures[fut]
            try:
                rec = fut.result()
            except Exception as exc:  # noqa: BLE001
                if buffer:
                    part_idx = _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, output_root)
                    buffer.clear()
                print(f"[openspatial-metadata] json_files worker failed: {ip}\n{exc!r}", file=sys.stderr)
                ex.shutdown(wait=True, cancel_futures=True)
                sys.exit(1)
            buffer.append(rec)
            if len(buffer) >= batch_size:
                part_idx = _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, output_root)
                buffer.clear()
        if buffer:
            _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, output_root)
            buffer.clear()
    finally:
        ex.shutdown(wait=True, cancel_futures=False)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="openspatial-metadata")
    p.add_argument("--config-root", required=True, help="Path to dataset config folder or a single yaml file.")
    p.add_argument("--global-config", default=None, help="Optional global.yaml with defaults.")
    p.add_argument("--output-root", default=None, help="Override output root (otherwise from global config).")
    p.add_argument("--resume", action="store_true", help="Resume from checkpoints.")
    p.add_argument("--num-workers", type=int, default=0, help="Number of workers (file-level parallel); 0 = use global.yaml num_workers.")
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    g = load_global_config(args.global_config)
    cli_workers = args.num_workers

    cfg_paths = discover_dataset_configs(args.config_root)
    _log(f"discovered {len(cfg_paths)} dataset config(s) under {args.config_root}")
    for cfg_path in cfg_paths:
        ds = load_dataset_config(cfg_path)
        resolve_adapter(ds)
        ds_output_root = args.output_root or getattr(ds, "output_root", None) or g.output_root
        output_root = Path(ds_output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        (rel2d, rel3d) = _get_enrich_flags(ds)
        if rel3d:
            raise ValueError("relations_3d enrich not implemented")
        for split in ds.splits:
            adapter_factory = _make_adapter_factory(
                ds,
                split_name=split.name,
                coord_space="norm_0_999",
                coord_scale=int(getattr(g, "scale", 1000)),
            )
            files = [Path(p) for p in expand_inputs(split.inputs)]
            out_dir = output_root / ds.name / split.name
            out_dir.mkdir(parents=True, exist_ok=True)
            eff = effective_parallel_workers(cli_workers, g.num_workers, len(files))
            _log(
                f"start {ds.name}/{split.name}: type={split.input_type} files={len(files)} workers={eff} "
                f"batch_size={g.batch_size} enrich2d={rel2d} out={out_dir}"
            )

            if split.input_type == "jsonl":
                if eff > 1:
                    _process_jsonl_files_parallel(
                        files,
                        out_dir,
                        effective=eff,
                        batch_size=g.batch_size,
                        resume=args.resume or g.resume,
                        strict=g.strict,
                        output_root=output_root,
                        adapter_factory=adapter_factory,
                        relations_2d=rel2d,
                        ds=ds,
                        split_name=split.name,
                        dataset_path=cfg_path,
                    )
                else:
                    for ip in files:
                        op = out_dir / (ip.stem + ".metadata.jsonl")
                        _log(f"{ds.name}/{split.name}: processing {ip}")
                        _process_jsonl_file(
                            ip,
                            op,
                            batch_size=g.batch_size,
                            resume=args.resume or g.resume,
                            strict=g.strict,
                            output_root=output_root,
                            adapter_factory=adapter_factory,
                            relations_2d=rel2d,
                            ds=ds,
                            split_name=split.name,
                            dataset_path=cfg_path,
                        )
                        _log(f"{ds.name}/{split.name}: done {ip.name}")
            elif split.input_type == "json_files":
                if eff > 1:
                    _process_json_files_parallel(
                        files,
                        out_dir,
                        effective=eff,
                        batch_size=g.batch_size,
                        resume=args.resume or g.resume,
                        output_root=output_root,
                        adapter_factory=adapter_factory,
                        relations_2d=rel2d,
                        ds=ds,
                        split_name=split.name,
                        dataset_path=cfg_path,
                    )
                else:
                    _process_json_files_sequential(
                        files,
                        out_dir,
                        batch_size=g.batch_size,
                        resume=args.resume or g.resume,
                        output_root=output_root,
                        adapter_factory=adapter_factory,
                        relations_2d=rel2d,
                        ds=ds,
                        split_name=split.name,
                        dataset_path=cfg_path,
                    )
            else:
                raise ValueError(f"Unknown input_type: {split.input_type}")


if __name__ == "__main__":
    main()
