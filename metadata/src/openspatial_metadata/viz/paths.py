from __future__ import annotations

import json
import os
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


def enumerate_metadata_jsonl(output_root: Path) -> List[Dict[str, Any]]:
    """
    List ``*.metadata.jsonl`` under ``output_root/{dataset}/{split}/`` (recursive),
    excluding ``.checkpoints`` directories.
    """
    root = output_root.resolve()
    if not root.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d != ".checkpoints"]
        rel_dir = Path(dirpath).resolve().relative_to(root)
        parts = rel_dir.parts
        # Only ``{output_root}/{dataset}/{split}/`` (no extra nesting).
        if len(parts) != 2:
            continue
        dataset_name, split_name = parts[0], parts[1]
        if any(p.startswith(".") for p in parts):
            continue
        for fn in sorted(filenames):
            if not fn.endswith(".metadata.jsonl"):
                continue
            full = Path(dirpath) / fn
            rel = full.resolve().relative_to(root)
            out.append(
                {
                    "path": str(full),
                    "rel_path": str(rel).replace("\\", "/"),
                    "dataset_dir": dataset_name,
                    "split": split_name,
                    "name": fn,
                }
            )
    out.sort(key=lambda x: x["rel_path"])
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
