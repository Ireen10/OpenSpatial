from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import import_module
from inspect import signature
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .adapters.chained import ChainedAdapter
from .config.loader import (
    adapter_specs_for_dataset,
    discover_dataset_configs,
    expand_inputs,
    load_dataset_config,
    load_global_config,
    resolve_adapter,
)
from .config.qa_tasks import build_qa_items, load_qa_tasks_config, resolve_qa_task_params
from .io.json import JsonlWriter, iter_json_file, iter_jsonl
from .schema.metadata_v0 import MetadataV0

PARALLEL_WORKERS_CAP = 32


def _md_validate(payload: Any) -> MetadataV0:
    """Pydantic v1/v2 compatible parse."""
    if hasattr(MetadataV0, "model_validate"):
        return MetadataV0.model_validate(payload)
    return MetadataV0.parse_obj(payload)


def _md_dump(md: MetadataV0) -> Dict[str, Any]:
    if hasattr(md, "model_dump"):
        return md.model_dump()
    return md.dict()


def _qa_item_dump(it: Any) -> Dict[str, Any]:
    if hasattr(it, "model_dump"):
        return it.model_dump()
    return it.dict()


def _metadata_output_jsonl_name(part_id: int) -> str:
    """
    Stable shard filename for metadata JSONL outputs: ``data_000000.jsonl``, …
    ``part_id`` is the 0-based index of the input file in the split ``inputs`` list.
    """
    return f"data_{int(part_id):06d}.jsonl"


_PROGRESS_MODE = "tqdm"  # "tqdm" | "log" | "none" (tqdm will fall back to log if unavailable)
_TQDM = None


def _log(msg: str) -> None:
    if _PROGRESS_MODE == "none":
        return
    prefix = f"[openspatial-metadata] {msg}"
    if _PROGRESS_MODE == "tqdm" and _TQDM is not None:
        _TQDM.write(prefix, file=sys.stderr)
        return
    print(prefix, file=sys.stderr, flush=True)


def _tqdm(*args, **kwargs):
    if _PROGRESS_MODE != "tqdm" or _TQDM is None:
        return None
    return _TQDM(*args, **kwargs)


def _instantiate_one_adapter(
    spec: Any,
    ds: Any,
    g: Optional[Any] = None,
    *,
    split_name: str,
    coord_space: str,
    coord_scale: int,
    dataset_config_path: Optional[str] = None,
) -> Optional[object]:
    module_name = spec.module
    class_name = spec.class_name or getattr(spec, "class_", None)
    if module_name is None and spec.file_name is not None:
        module_name = f"openspatial_metadata.adapters.{spec.file_name}"
    if module_name is None or class_name is None:
        return None

    mod = import_module(module_name)
    cls = getattr(mod, class_name)
    spec_params = getattr(spec, "params", None)
    if not isinstance(spec_params, dict):
        spec_params = {}
    global_llm = getattr(g, "llm", None) if g is not None else None
    if not isinstance(global_llm, dict):
        global_llm = {}

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

        # global.llm defaults (only for ctor params that exist on this adapter)
        for k, v in global_llm.items():
            if k not in params:
                continue
            if k == "image_root" and isinstance(v, str):
                kwargs[k] = _resolve_path_under_dataset_config(v, dataset_config_path)
            else:
                kwargs[k] = v

        # AdapterSpec.params overrides global.llm
        for k, v in spec_params.items():
            if k not in params:
                continue
            if k == "image_root" and isinstance(v, str):
                kwargs[k] = _resolve_path_under_dataset_config(v, dataset_config_path)
            else:
                kwargs[k] = v

        if "image_root" in params and "image_root" not in kwargs and dataset_config_path:
            kwargs["image_root"] = _resolved_image_root_for_adapter(ds, dataset_config_path)
    except Exception:
        kwargs = {}

    if kwargs:
        try:
            return cls(**kwargs)
        except TypeError:
            pass
    return cls()


def _make_adapter_factory(
    ds: Any,
    g: Optional[Any] = None,
    *,
    split_name: str,
    coord_space: str,
    coord_scale: int,
    dataset_config_path: Optional[str] = None,
) -> Callable[[], Optional[object]]:
    """
    Build a per-call adapter factory. Returns None when no adapter spec present.
    Multiple specs become a ChainedAdapter (same constructor injection per step).
    """
    specs = adapter_specs_for_dataset(ds)
    if not specs:
        return lambda: None

    def _factory() -> Optional[object]:
        instances: List[object] = []
        for spec in specs:
            inst = _instantiate_one_adapter(
                spec,
                ds,
                g,
                split_name=split_name,
                coord_space=coord_space,
                coord_scale=coord_scale,
                dataset_config_path=dataset_config_path,
            )
            if inst is not None:
                instances.append(inst)
        if not instances:
            return None
        if len(instances) == 1:
            return instances[0]
        chain_kw: Dict[str, Any] = {}
        ac = getattr(ds, "adapter_chain", None)
        if ac is not None:
            chain_kw["strict_dict"] = bool(getattr(ac, "strict_dict", True))
            vm = getattr(ac, "validate_metadata_from_adapter_index", None)
            chain_kw["validate_metadata_from_adapter_index"] = int(vm) if vm is not None else None
        return ChainedAdapter(instances, **chain_kw)

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

    md = _md_validate(out)
    md2 = enrich_relations_2d(md)
    return _md_dump(md2)


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


def _checkpoint_key(input_file: str) -> str:
    import hashlib

    return hashlib.md5(input_file.encode("utf-8")).hexdigest()  # nosec: non-crypto usage


def _checkpoint_path(checkpoint_root: Path, input_file: str) -> Path:
    h = _checkpoint_key(input_file)
    return checkpoint_root / f"{h}.json"


def _read_checkpoint(path: Path, *, fallback: Optional[Path] = None) -> Optional[Dict]:
    if not path.exists():
        if fallback is None or not fallback.exists():
            return None
        return json.loads(fallback.read_text(encoding="utf-8"))
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
    max_records: Optional[int] = None,
    resume: bool,
    strict: bool,
    output_root: Path,
    checkpoint_root: Path,
    tqdm_pos: Optional[int] = None,
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
) -> int:
    del strict  # reserved for future per-record error policy
    if max_records is not None:
        max_records = int(max_records)
        if max_records <= 0:
            return 0
    ckpt_path = _checkpoint_path(checkpoint_root, str(input_path))
    old_ckpt_path = _checkpoint_path(output_root / ".checkpoints", str(input_path))
    ckpt = _read_checkpoint(ckpt_path, fallback=old_ckpt_path) if resume else None
    next_idx = int(ckpt.get("next_input_index", 0)) if ckpt else 0

    buffer: List[Dict] = []
    adapter = adapter_factory()
    bar = None
    processed = 0
    processed_this_run = 0
    if _PROGRESS_MODE == "tqdm":
        bar = _tqdm(
            total=None,
            position=tqdm_pos or 0,
            desc=f"{ds.name}/{split_name} {input_path.name}",
            unit="rec",
            dynamic_ncols=True,
            leave=False,
        )
        if bar is not None and next_idx > 0:
            bar.update(next_idx)
            processed = next_idx
    with JsonlWriter(output_path, append=resume and output_path.exists()) as w:
        for record, ref in iter_jsonl(input_path):
            if ref.input_index < next_idx:
                continue
            if max_records is not None and processed_this_run >= max_records:
                break
            out = _apply_adapter(adapter, record)
            out.setdefault("aux", {})
            out["aux"]["record_ref"] = {"input_file": ref.input_file, "input_index": ref.input_index}
            out = _apply_dataset_meta(out, ds=ds, split_name=split_name, dataset_path=dataset_path)
            out = _apply_enrich_if_enabled(out, relations_2d=relations_2d)
            buffer.append(out)
            if bar is not None:
                bar.update(1)
                processed += 1
            processed_this_run += 1
            if len(buffer) >= batch_size:
                w.write_records(buffer)
                w.flush()
                next_idx = ref.input_index + 1
                if bar is None:
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
            if bar is None:
                _log(f"{ds.name}/{split_name}: {input_path.name} processed={next_idx}")
            _write_checkpoint_atomic(
                ckpt_path,
                {"input_file": str(input_path), "next_input_index": next_idx, "errors_count": 0},
            )
    if bar is not None:
        bar.close()
    return processed_this_run


def _split_subdir(out_dir: Path, sub: str) -> Path:
    p = out_dir / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def _training_output_root(args_output_root: Optional[str], ds: Any, g: Any) -> Path:
    # training_output_root: dataset overrides global; fallback to metadata output root tree if absent
    tor = getattr(ds, "training_output_root", None)
    if isinstance(args_output_root, str) and args_output_root:
        # CLI --output-root overrides metadata output root only; training root uses dataset.training_output_root when set
        pass
    if isinstance(tor, str) and tor:
        return Path(tor)
    gtor = getattr(g, "training_output_root", None)
    if isinstance(gtor, str) and gtor:
        return Path(gtor)
    return Path(args_output_root or getattr(ds, "metadata_output_root", None) or g.metadata_output_root)


def _resolve_image_root(ds: Any, dataset_path: str) -> str:
    viz = getattr(ds, "viz", None)
    ir = getattr(viz, "image_root", None) if viz is not None else None
    if isinstance(ir, str) and ir:
        return ir
    return str(Path(dataset_path).parent)


def _resolve_path_under_dataset_config(path_str: str, dataset_config_path: Optional[str]) -> str:
    p = Path(path_str)
    if p.is_absolute() or not dataset_config_path:
        return str(p)
    return str((Path(dataset_config_path).resolve().parent / p).resolve())


def _resolved_image_root_for_adapter(ds: Any, dataset_config_path: str) -> str:
    """Absolute image root for filesystem reads (same rules as ``_resolve_image_root``)."""
    base = _resolve_image_root(ds, dataset_config_path)
    p = Path(base)
    if not p.is_absolute():
        p = Path(dataset_config_path).resolve().parent / p
    return str(p.resolve())


def _training_pack_settings(g: Any, pipe: Optional[Dict[str, Any]]) -> Tuple[int, int]:
    rows = int(getattr(g, "training_rows_per_part", 1024) or 1024)
    align = int(getattr(g, "training_row_align", 16) or 16)
    if isinstance(pipe, dict):
        if pipe.get("training_rows_per_part") is not None:
            rows = int(pipe["training_rows_per_part"])
        if pipe.get("training_row_align") is not None:
            align = int(pipe["training_row_align"])
    return rows, align


def _finalize_training_export_for_split(
    *,
    enable_export: bool,
    output_root: Path,
    training_root: Path,
    ds: Any,
    split_name: str,
    dataset_path: str,
    rows_per_part: int,
    row_align: int,
) -> None:
    if not enable_export:
        return
    from .export.training_pack import export_training_bundles_for_split

    bar = None

    def on_shard_progress(si: int, n_shards: int, shard_path: Path) -> None:
        nonlocal bar
        if _PROGRESS_MODE == "none":
            return
        if _PROGRESS_MODE == "tqdm" and _TQDM is not None:
            if bar is None:
                bar = _tqdm(
                    total=n_shards,
                    desc=f"training export {ds.name}/{split_name}",
                    unit="shard",
                    dynamic_ncols=True,
                    leave=False,
                )
            bar.update(1)
            return
        _log(f"training export {ds.name}/{split_name}: shard {si + 1}/{n_shards} {shard_path.name}")

    try:
        n = export_training_bundles_for_split(
            output_root=output_root,
            training_root=training_root,
            dataset_name=ds.name,
            split_name=split_name,
            image_root=_resolve_image_root(ds, dataset_path),
            rows_per_part=rows_per_part,
            row_align=row_align,
            on_shard_progress=on_shard_progress,
        )
    finally:
        if bar is not None:
            bar.close()
    _log(
        f"training export {ds.name}/{split_name}: wrote {n} bundle(s) "
        f"(rows_per_part={rows_per_part}, row_align={row_align})"
    )


def _process_jsonl_file_training_pipeline(
    input_path: Path,
    *,
    part_id: int,
    resume: bool,
    output_root: Path,
    checkpoint_root: Path,
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
    qa_registry: Dict[str, Any],
    qa_task_name: str,
    qa_task_overrides: Optional[Dict[str, Any]],
    enable_to_metadata: bool,
    enable_ensure_qa: bool,
    max_records: Optional[int] = None,
    tqdm_pos: Optional[int] = None,
) -> int:
    """
    One input jsonl file -> metadata_noqa / metadata_qa shards (``data_{part_id}.jsonl``).
    Training bundles are produced in a separate pass after all input shards complete.
    """
    ckpt_path = _checkpoint_path(checkpoint_root, str(input_path))
    old_ckpt_path = _checkpoint_path(output_root / ".checkpoints", str(input_path))
    ckpt = _read_checkpoint(ckpt_path, fallback=old_ckpt_path) if resume else None
    next_idx = int(ckpt.get("next_input_index", 0)) if ckpt else 0
    if max_records is not None:
        max_records = int(max_records)
        if max_records <= 0:
            return 0

    # Metadata outputs: {output_root}/{ds}/{split}/{metadata_noqa|metadata_qa}/data_{part_id:06d}.jsonl
    split_out = output_root / ds.name / split_name
    noq_dir = _split_subdir(split_out, "metadata_noqa")
    qa_dir = _split_subdir(split_out, "metadata_qa")
    shard = _metadata_output_jsonl_name(part_id)
    noq_path = noq_dir / shard
    qa_path = qa_dir / shard

    adapter = adapter_factory()
    qa_params = resolve_qa_task_params(qa_registry, qa_task_name=qa_task_name, overrides=qa_task_overrides)

    checkpoint_root.mkdir(parents=True, exist_ok=True)

    bar = None
    processed_this_run = 0
    if _PROGRESS_MODE == "tqdm":
        bar = _tqdm(
            total=None,
            position=tqdm_pos or 0,
            desc=f"{ds.name}/{split_name} {input_path.name}",
            unit="rec",
            dynamic_ncols=True,
            leave=False,
        )
        if bar is not None and next_idx > 0:
            bar.update(next_idx)

    try:
        with JsonlWriter(noq_path, append=resume and noq_path.exists()) as w_noq, JsonlWriter(
            qa_path, append=resume and qa_path.exists()
        ) as w_qa:
            for record, ref in iter_jsonl(input_path):
                if ref.input_index < next_idx:
                    continue
                if max_records is not None and processed_this_run >= max_records:
                    break

                # Step 1: to_metadata (adapter + dataset meta + enrich)
                if enable_to_metadata:
                    out = _apply_adapter(adapter, record)
                    out.setdefault("aux", {})
                    out["aux"]["record_ref"] = {"input_file": ref.input_file, "input_index": ref.input_index}
                    out = _apply_dataset_meta(out, ds=ds, split_name=split_name, dataset_path=dataset_path)
                    out = _apply_enrich_if_enabled(out, relations_2d=relations_2d)
                else:
                    out = dict(record)

                md_noqa = _md_validate(out)

                # Step 2: ensure_qa (metadata-native QA generator)
                md_qa = md_noqa
                if enable_ensure_qa and not md_noqa.qa_items:
                    items = build_qa_items(md_noqa, qa_task_name=qa_task_name, params=qa_params)
                    payload = _md_dump(md_noqa)
                    payload["qa_items"] = [_qa_item_dump(it) for it in items]
                    md_qa = _md_validate(payload)

                # Always persist the noqa view (one line per input record). When qa_items is empty, skip
                # metadata_qa and training export for that record (export still requires non-empty qa_items).
                w_noq.write_records([_md_dump(md_noqa)])

                # Persist the "qa" view only when there is at least 1 QA item.
                if md_qa.qa_items:
                    w_qa.write_records([_md_dump(md_qa)])

                next_idx = ref.input_index + 1
                _write_checkpoint_atomic(
                    ckpt_path, {"input_file": str(input_path), "next_input_index": next_idx, "errors_count": 0}
                )

                if bar is not None:
                    bar.update(1)
                elif _PROGRESS_MODE == "log" and (next_idx % 1000 == 0):
                    _log(f"{ds.name}/{split_name}: {input_path.name} processed={next_idx}")
                processed_this_run += 1
    finally:
        if bar is not None:
            bar.close()
    return processed_this_run


def _process_jsonl_files_parallel(
    files: List[Path],
    out_dir: Path,
    *,
    effective: int,
    batch_size: int,
    resume: bool,
    strict: bool,
    output_root: Path,
    checkpoint_root: Path,
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ex = ThreadPoolExecutor(max_workers=effective)
    futures: Dict[Any, Tuple[Path, int]] = {}
    slots = list(range(max(1, effective)))
    pending = list(enumerate(files))
    try:
        # Submit up to `effective` tasks, each holding a unique progress slot.
        while pending and slots:
            slot = slots.pop(0)
            part_id, ip = pending.pop(0)
            op = out_dir / _metadata_output_jsonl_name(part_id)
            fut = ex.submit(
                _process_jsonl_file,
                ip,
                op,
                batch_size=batch_size,
                resume=resume,
                strict=strict,
                output_root=output_root,
                checkpoint_root=checkpoint_root,
                tqdm_pos=slot,
                adapter_factory=adapter_factory,
                relations_2d=relations_2d,
                ds=ds,
                split_name=split_name,
                dataset_path=dataset_path,
            )
            futures[fut] = (ip, slot)

        while futures:
            for fut in as_completed(list(futures.keys())):
                ip, slot = futures.pop(fut)
                try:
                    fut.result()
                    _log(f"{ds.name}/{split_name}: done {ip.name}")
                except Exception as exc:  # noqa: BLE001 — surface to user under strict
                    print(f"[openspatial-metadata] JSONL worker failed: {ip}\n{exc!r}", file=sys.stderr)
                    ex.shutdown(wait=True, cancel_futures=True)
                    sys.exit(1)
                slots.append(slot)
                if pending:
                    slot = slots.pop(0)
                    part_id, nip = pending.pop(0)
                    op = out_dir / _metadata_output_jsonl_name(part_id)
                    nfut = ex.submit(
                        _process_jsonl_file,
                        nip,
                        op,
                        batch_size=batch_size,
                        resume=resume,
                        strict=strict,
                        output_root=output_root,
                        checkpoint_root=checkpoint_root,
                        tqdm_pos=slot,
                        adapter_factory=adapter_factory,
                        relations_2d=relations_2d,
                        ds=ds,
                        split_name=split_name,
                        dataset_path=dataset_path,
                    )
                    futures[nfut] = (nip, slot)
                break
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
    checkpoint_root: Path,
) -> int:
    """Write one data_*.jsonl shard and mark done checkpoint for each record's source file."""
    if not buffer:
        return part_idx
    out_path = out_dir / _metadata_output_jsonl_name(part_idx)
    with JsonlWriter(out_path, append=False) as w:
        w.write_records(buffer)
        w.flush()
    for rec in buffer:
        src = rec.get("aux", {}).get("record_ref", {}).get("input_file")
        if src:
            _write_checkpoint_atomic(
                _checkpoint_path(checkpoint_root, str(src)),
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
    checkpoint_root: Path,
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
        ckpt_path = _checkpoint_path(checkpoint_root, str(ip))
        old_ckpt_path = _checkpoint_path(output_root / ".checkpoints", str(ip))
        ckpt = _read_checkpoint(ckpt_path, fallback=old_ckpt_path) if resume else None
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
            part_idx = _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, checkpoint_root)
            buffer.clear()
    if buffer:
        _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, checkpoint_root)


def _process_json_files_parallel(
    input_files: List[Path],
    out_dir: Path,
    *,
    effective: int,
    batch_size: int,
    resume: bool,
    output_root: Path,
    checkpoint_root: Path,
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pending: List[Path] = []
    for ip in input_files:
        ckpt_path = _checkpoint_path(checkpoint_root, str(ip))
        old_ckpt_path = _checkpoint_path(output_root / ".checkpoints", str(ip))
        ckpt = _read_checkpoint(ckpt_path, fallback=old_ckpt_path) if resume else None
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
                    part_idx = _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, checkpoint_root)
                    buffer.clear()
                print(f"[openspatial-metadata] json_files worker failed: {ip}\n{exc!r}", file=sys.stderr)
                ex.shutdown(wait=True, cancel_futures=True)
                sys.exit(1)
            buffer.append(rec)
            if len(buffer) >= batch_size:
                part_idx = _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, checkpoint_root)
                buffer.clear()
        if buffer:
            _flush_json_files_buffer_with_checkpoints(buffer, out_dir, part_idx, checkpoint_root)
            buffer.clear()
    finally:
        ex.shutdown(wait=True, cancel_futures=False)


def _pipeline_flags(ds: Any) -> Optional[Dict[str, Any]]:
    """
    Dataset-level pipeline config. Kept flexible (extra=allow), so we accept:
    - None / missing -> no pipeline, default metadata-only behavior
    - dict with keys {to_metadata, ensure_qa, export_training, qa_task_name, qa_task_overrides,
      training_rows_per_part, training_row_align} (latter two override global defaults for export only)
    """
    p = getattr(ds, "pipelines", None)
    if p is None:
        return None
    if isinstance(p, dict):
        return p
    if isinstance(p, list) and p:
        # If multiple pipelines are provided, pick the first for now.
        v0 = p[0]
        return v0 if isinstance(v0, dict) else None
    return None


def _process_jsonl_files_training_parallel(
    files: List[Path],
    *,
    effective: int,
    resume: bool,
    output_root: Path,
    checkpoint_root: Path,
    adapter_factory: Callable[[], Optional[object]],
    relations_2d: bool,
    ds: Any,
    split_name: str,
    dataset_path: str,
    qa_registry: Dict[str, Any],
    qa_task_name: str,
    qa_task_overrides: Optional[Dict[str, Any]],
    enable_to_metadata: bool,
    enable_ensure_qa: bool,
) -> None:
    ex = ThreadPoolExecutor(max_workers=effective)
    futures: Dict[Any, Tuple[Path, int, int]] = {}
    slots = list(range(max(1, effective)))
    pending = list(enumerate(files))
    try:
        while pending and slots:
            slot = slots.pop(0)
            part_id, ip = pending.pop(0)
            fut = ex.submit(
                _process_jsonl_file_training_pipeline,
                ip,
                part_id=part_id,
                resume=resume,
                output_root=output_root,
                checkpoint_root=checkpoint_root,
                adapter_factory=adapter_factory,
                relations_2d=relations_2d,
                ds=ds,
                split_name=split_name,
                dataset_path=dataset_path,
                qa_registry=qa_registry,
                qa_task_name=qa_task_name,
                qa_task_overrides=qa_task_overrides,
                enable_to_metadata=enable_to_metadata,
                enable_ensure_qa=enable_ensure_qa,
                tqdm_pos=slot,
            )
            futures[fut] = (ip, part_id, slot)

        while futures:
            for fut in as_completed(list(futures.keys())):
                ip, part_id, slot = futures.pop(fut)
                try:
                    fut.result()
                    _log(f"{ds.name}/{split_name}: done part={part_id} {ip.name}")
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"[openspatial-metadata] pipeline worker failed: {ds.name}/{split_name} part={part_id} file={ip}\n{exc!r}",
                        file=sys.stderr,
                    )
                    ex.shutdown(wait=True, cancel_futures=True)
                    sys.exit(1)
                slots.append(slot)
                if pending:
                    slot2 = slots.pop(0)
                    part_id2, ip2 = pending.pop(0)
                    nfut = ex.submit(
                        _process_jsonl_file_training_pipeline,
                        ip2,
                        part_id=part_id2,
                        resume=resume,
                        output_root=output_root,
                        checkpoint_root=checkpoint_root,
                        adapter_factory=adapter_factory,
                        relations_2d=relations_2d,
                        ds=ds,
                        split_name=split_name,
                        dataset_path=dataset_path,
                        qa_registry=qa_registry,
                        qa_task_name=qa_task_name,
                        qa_task_overrides=qa_task_overrides,
                        enable_to_metadata=enable_to_metadata,
                        enable_ensure_qa=enable_ensure_qa,
                        tqdm_pos=slot2,
                    )
                    futures[nfut] = (ip2, part_id2, slot2)
                break
    finally:
        ex.shutdown(wait=True, cancel_futures=False)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="openspatial-metadata")
    p.add_argument("--config-root", required=True, help="Path to dataset config folder or a single yaml file.")
    p.add_argument("--global-config", default=None, help="Optional global.yaml with defaults.")
    p.add_argument(
        "--qa-config",
        default=None,
        help="Optional qa_tasks.yaml (overrides global.yaml.qa_config).",
    )
    p.add_argument("--output-root", default=None, help="Override output root (otherwise from global config).")
    p.add_argument("--resume", action="store_true", help="Resume from checkpoints.")
    p.add_argument("--num-workers", type=int, default=0, help="Number of workers (file-level parallel); 0 = use global.yaml num_workers.")
    p.add_argument(
        "--max-records-per-split",
        type=int,
        default=0,
        help="If >0, process at most N records per dataset split (forces sequential execution for determinism).",
    )
    p.add_argument(
        "--max-records-total",
        type=int,
        default=0,
        help="If >0, process at most N records across all discovered datasets/splits (forces sequential execution).",
    )
    p.add_argument("--progress", choices=["tqdm", "log", "none"], default="tqdm", help="Progress display mode.")
    return p


def main(argv=None) -> None:
    global _PROGRESS_MODE, _TQDM
    args = build_parser().parse_args(argv)
    _PROGRESS_MODE = args.progress
    if _PROGRESS_MODE == "tqdm":
        try:
            from tqdm import tqdm as _real_tqdm  # type: ignore

            _TQDM = _real_tqdm
        except Exception:
            _TQDM = None
            _PROGRESS_MODE = "log"
            _log("tqdm not available; falling back to log progress")
    g = load_global_config(args.global_config)
    cli_workers = args.num_workers
    max_records_per_split = int(getattr(args, "max_records_per_split", 0) or 0)
    max_records_total = int(getattr(args, "max_records_total", 0) or 0)
    remaining_total: Optional[int] = max_records_total if max_records_total > 0 else None
    qa_config_path = args.qa_config or getattr(g, "qa_config", None)
    qa_registry: Dict[str, Any] = {}
    if qa_config_path:
        try:
            qa_registry = load_qa_tasks_config(qa_config_path)
            _log(f"loaded qa_tasks from {qa_config_path}")
        except Exception as exc:
            raise ValueError(f"Failed to load qa_tasks config: {qa_config_path}") from exc

    cfg_paths = discover_dataset_configs(args.config_root)
    _log(f"discovered {len(cfg_paths)} dataset config(s) under {args.config_root}")
    for cfg_path in cfg_paths:
        if remaining_total is not None and remaining_total <= 0:
            break
        ds = load_dataset_config(cfg_path)
        resolve_adapter(ds)
        ds_output_root = args.output_root or getattr(ds, "metadata_output_root", None) or g.metadata_output_root
        output_root = Path(ds_output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        (rel2d, rel3d) = _get_enrich_flags(ds)
        if rel3d:
            raise ValueError("relations_3d enrich not implemented")
        for split in ds.splits:
            if remaining_total is not None and remaining_total <= 0:
                break
            adapter_factory = _make_adapter_factory(
                ds,
                g,
                split_name=split.name,
                coord_space="norm_0_999",
                coord_scale=int(getattr(g, "scale", 1000)),
                dataset_config_path=str(cfg_path),
            )
            files = [Path(p) for p in expand_inputs(split.inputs)]
            remaining: Optional[int] = None
            if max_records_per_split > 0:
                remaining = max_records_per_split
            if remaining_total is not None:
                remaining = remaining_total if remaining is None else min(remaining, remaining_total)
            out_dir = output_root / ds.name / split.name
            out_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_root = out_dir / ".checkpoints"
            eff = effective_parallel_workers(cli_workers, g.num_workers, len(files))
            if remaining is not None:
                eff = 1
            resume = args.resume or g.resume
            pipe = _pipeline_flags(ds)
            _log(
                f"start {ds.name}/{split.name}: type={split.input_type} files={len(files)} workers={eff} "
                f"batch_size={g.batch_size} enrich2d={rel2d} out={out_dir}"
            )

            if split.input_type == "jsonl":
                if pipe and bool(pipe.get("ensure_qa", False) or pipe.get("export_training", False)):
                    qa_task_name = str(pipe.get("qa_task_name") or "spatial_relation_2d")
                    qa_task_overrides = pipe.get("qa_task_overrides") if isinstance(pipe.get("qa_task_overrides"), dict) else None
                    enable_to_metadata = bool(pipe.get("to_metadata", True))
                    enable_ensure_qa = bool(pipe.get("ensure_qa", True))
                    enable_export = bool(pipe.get("export_training", True))
                    training_root = _training_output_root(args.output_root, ds, g)
                    rows_pt, row_al = _training_pack_settings(g, pipe)
                    _log(
                        f"pipeline {ds.name}/{split.name}: to_metadata={enable_to_metadata} "
                        f"ensure_qa={enable_ensure_qa} export_training={enable_export} qa_task={qa_task_name} "
                        f"train_out={training_root} training_rows_per_part={rows_pt} training_row_align={row_al}"
                    )
                    if eff > 1:
                        _process_jsonl_files_training_parallel(
                            files,
                            effective=eff,
                            resume=resume,
                            output_root=output_root,
                            checkpoint_root=checkpoint_root,
                            adapter_factory=adapter_factory,
                            relations_2d=rel2d,
                            ds=ds,
                            split_name=split.name,
                            dataset_path=cfg_path,
                            qa_registry=qa_registry,
                            qa_task_name=qa_task_name,
                            qa_task_overrides=qa_task_overrides,
                            enable_to_metadata=enable_to_metadata,
                            enable_ensure_qa=enable_ensure_qa,
                        )
                    else:
                        for part_id, ip in enumerate(files):
                            if remaining is not None and remaining <= 0:
                                break
                            _log(f"{ds.name}/{split.name}: processing part={part_id} {ip}")
                            n_done = _process_jsonl_file_training_pipeline(
                                ip,
                                part_id=part_id,
                                resume=resume,
                                output_root=output_root,
                                checkpoint_root=checkpoint_root,
                                adapter_factory=adapter_factory,
                                relations_2d=rel2d,
                                ds=ds,
                                split_name=split.name,
                                dataset_path=cfg_path,
                                qa_registry=qa_registry,
                                qa_task_name=qa_task_name,
                                qa_task_overrides=qa_task_overrides,
                                enable_to_metadata=enable_to_metadata,
                                enable_ensure_qa=enable_ensure_qa,
                                max_records=remaining,
                                tqdm_pos=0,
                            )
                            _log(f"{ds.name}/{split.name}: done {ip.name}")
                            if remaining is not None:
                                remaining -= int(n_done)
                                if remaining_total is not None:
                                    remaining_total = remaining
                    _finalize_training_export_for_split(
                        enable_export=enable_export,
                        output_root=output_root,
                        training_root=training_root,
                        ds=ds,
                        split_name=split.name,
                        dataset_path=cfg_path,
                        rows_per_part=rows_pt,
                        row_align=row_al,
                    )
                else:
                    if eff > 1:
                        _process_jsonl_files_parallel(
                            files,
                            out_dir,
                            effective=eff,
                            batch_size=g.batch_size,
                            resume=resume,
                            strict=g.strict,
                            output_root=output_root,
                            checkpoint_root=checkpoint_root,
                            adapter_factory=adapter_factory,
                            relations_2d=rel2d,
                            ds=ds,
                            split_name=split.name,
                            dataset_path=cfg_path,
                        )
                    else:
                        for part_id, ip in enumerate(files):
                            if remaining is not None and remaining <= 0:
                                break
                            op = out_dir / _metadata_output_jsonl_name(part_id)
                            _log(f"{ds.name}/{split.name}: processing {ip}")
                            n_done = _process_jsonl_file(
                                ip,
                                op,
                                batch_size=g.batch_size,
                                max_records=remaining,
                                resume=resume,
                                strict=g.strict,
                                output_root=output_root,
                                checkpoint_root=checkpoint_root,
                                adapter_factory=adapter_factory,
                                relations_2d=rel2d,
                                ds=ds,
                                split_name=split.name,
                                dataset_path=cfg_path,
                            )
                            _log(f"{ds.name}/{split.name}: done {ip.name}")
                            if remaining is not None:
                                remaining -= int(n_done)
                                if remaining_total is not None:
                                    remaining_total = remaining
            elif split.input_type == "json_files":
                if remaining is not None:
                    files = files[:remaining]
                    if remaining_total is not None:
                        remaining_total -= len(files)
                if eff > 1:
                    _process_json_files_parallel(
                        files,
                        out_dir,
                        effective=eff,
                        batch_size=g.batch_size,
                        resume=resume,
                        output_root=output_root,
                        checkpoint_root=checkpoint_root,
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
                        resume=resume,
                        output_root=output_root,
                        checkpoint_root=checkpoint_root,
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
