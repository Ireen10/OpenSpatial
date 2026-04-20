from __future__ import annotations

import json
import os
import re
import mimetypes
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


def is_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_file_under_root(candidate: Path, root: Path) -> Optional[Path]:
    """Return resolved path if it exists and lies under root, else None."""
    try:
        root_r = root.resolve()
        cand = candidate.resolve()
        cand.relative_to(root_r)
    except ValueError:
        return None
    except OSError:
        return None
    if not cand.is_file():
        return None
    return cand


_METADATA_JSONL_LEGACY_SUFFIX = ".metadata.jsonl"
_DATA_JSONL_RE = re.compile(r"^data_\d{6}\.jsonl$")


def _is_metadata_stage_jsonl_filename(fn: str) -> bool:
    """CLI metadata shards: ``data_000000.jsonl`` or legacy ``*.metadata.jsonl``."""
    if fn.endswith(_METADATA_JSONL_LEGACY_SUFFIX):
        return True
    return bool(_DATA_JSONL_RE.match(fn))


def enumerate_metadata_jsonl(output_root: Path) -> List[Dict[str, Any]]:
    """
    List metadata JSONL shards under ``output_root/{dataset}/{split}/...`` (recursive),
    excluding ``.checkpoints`` directories.

    Filenames: ``data_{:06d}.jsonl`` (current CLI) or legacy ``*.metadata.jsonl``.

    Emits stage as:
    - ``metadata_noqa`` / ``metadata_qa`` when the 3rd path component matches
    - otherwise ``flat``
    """
    root = output_root.resolve()
    if not root.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d != ".checkpoints"]
        rel_dir = Path(dirpath).resolve().relative_to(root)
        parts = rel_dir.parts
        # Require at least ``{output_root}/{dataset}/{split}/``.
        if len(parts) < 2:
            continue
        dataset_name, split_name = parts[0], parts[1]
        if any(p.startswith(".") for p in parts):
            continue
        stage = "flat"
        if len(parts) >= 3 and parts[2] in ("metadata_noqa", "metadata_qa"):
            stage = parts[2]
        for fn in sorted(filenames):
            if not _is_metadata_stage_jsonl_filename(fn):
                continue
            full = Path(dirpath) / fn
            rel = full.resolve().relative_to(root)
            out.append(
                {
                    "path": str(full),
                    "rel_path": str(rel).replace("\\", "/"),
                    "dataset_dir": dataset_name,
                    "split": split_name,
                    "stage": stage,
                    "name": fn,
                }
            )
    out.sort(key=lambda x: x["rel_path"])
    return out


def enumerate_training_parts(training_root: Path) -> List[Dict[str, Any]]:
    """
    Enumerate training bundles under:
      {training_root}/{dataset}/{split}/{images,jsonl}/data_{id:06d}.*

    Returns entries with keys: dataset, split, part_id, jsonl_rel, tar_rel, tarinfo_rel.

    Note: this function expects ``training_root`` to be the **bundle root** that
    already contains ``{dataset}/{split}/...`` (i.e. it is dataset.training_output_root).
    """
    root = training_root.resolve()
    if not root.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for dataset_dir in sorted([p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]):
        for split_dir in sorted([p for p in dataset_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]):
            images_dir = split_dir / "images"
            jsonl_dir = split_dir / "jsonl"
            if not images_dir.is_dir() or not jsonl_dir.is_dir():
                continue
            # list jsonl parts; require corresponding tar and tarinfo
            for jp in sorted(jsonl_dir.glob("data_*.jsonl")):
                m = re.match(r"^data_(\d{6})\.jsonl$", jp.name)
                if not m:
                    continue
                pid = int(m.group(1))
                tp = images_dir / f"data_{pid:06d}.tar"
                tip = images_dir / f"data_{pid:06d}_tarinfo.json"
                if not tp.is_file() or not tip.is_file():
                    continue
                out.append(
                    {
                        "dataset": dataset_dir.name,
                        "split": split_dir.name,
                        "part_id": pid,
                        "jsonl_rel": str(jp.resolve().relative_to(root)).replace("\\", "/"),
                        "tar_rel": str(tp.resolve().relative_to(root)).replace("\\", "/"),
                        "tarinfo_rel": str(tip.resolve().relative_to(root)).replace("\\", "/"),
                    }
                )
    out.sort(key=lambda x: (x["dataset"], x["split"], x["part_id"]))
    return out


def count_lines_jsonl(path: Path) -> int:
    n = 0
    with path.open("rb") as f:
        for _ in f:
            n += 1
    return n


def read_line_jsonl(path: Path, line_index: int) -> Dict[str, Any]:
    """0-based line index."""
    if line_index < 0:
        raise ValueError("line_index must be >= 0")
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == line_index:
                line = line.strip()
                if not line:
                    raise ValueError("empty line")
                return json.loads(line)
    raise IndexError("line index out of range")


def read_lines_jsonl(path: Path, *, offset: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
    """
    Read a window of JSONL lines. Returns (records, total_line_count).
    Enforces offset>=0, limit>=1.
    """
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit <= 0:
        raise ValueError("limit must be >= 1")
    total = 0
    out: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            total += 1
            if i < offset:
                continue
            if i >= offset + limit:
                continue
            s = line.strip()
            if not s:
                continue
            out.append(json.loads(s))
    return out, total


def read_tar_member_by_tarinfo(tar_path: Path, *, offset_data: int, size: int) -> bytes:
    """
    Read bytes slice from tar without extracting:
    - seek to offset_data (start of member payload)
    - read size bytes (payload length)
    """
    if offset_data < 0 or size < 0:
        raise ValueError("offset_data/size must be >= 0")
    with tar_path.open("rb") as f:
        f.seek(int(offset_data))
        data = f.read(int(size))
    if len(data) != int(size):
        raise OSError("unexpected end of data while reading tar member")
    return data


def guess_content_type_from_name(name: str) -> str:
    mime, _ = mimetypes.guess_type(name)
    return mime or "application/octet-stream"


def find_sample_line(path: Path, sample_id: str) -> int:
    """Return 0-based line index of first record with ``sample.sample_id == sample_id``."""
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = obj.get("sample", {}).get("sample_id")
            if sid == sample_id:
                return i
    raise KeyError(sample_id)


def iter_lines(path: Path) -> Iterator[Tuple[int, Dict[str, Any]]]:
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            yield i, json.loads(line)
