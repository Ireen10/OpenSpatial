#!/usr/bin/env python3
"""
Count samples and QA turns in an exported training dataset.

A *sample* is one non-empty JSON line in ``jsonl/data_*.jsonl``.
*QA count* is the number of assistant turns per row (one per QA item in the visual group),
summed across all rows — matching ``build_training_line`` / multi-turn chat format.

Usage::

    python metadata/scripts/count_training_dataset.py path/to/training/<dataset>/<split>
    python metadata/scripts/count_training_dataset.py path/to/jsonl_dir   # if dir is named jsonl or contains data_*.jsonl

The path should be the split directory that contains a ``jsonl/`` subfolder (as produced by
``export_training``), or a ``jsonl`` directory, or a single ``*.jsonl`` file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


def _resolve_jsonl_files(root: Path) -> List[Path]:
    if root.is_file():
        if root.suffix.lower() == ".jsonl":
            return [root]
        raise ValueError(f"Not a .jsonl file: {root}")

    jl = root / "jsonl"
    if jl.is_dir():
        files = sorted(jl.glob("data_*.jsonl"))
        if files:
            return files
    if root.name == "jsonl" and root.is_dir():
        files = sorted(root.glob("data_*.jsonl"))
        if files:
            return files

    raise ValueError(
        f"No training jsonl found under {root}: expected .../<split>/jsonl/data_*.jsonl "
        "or a path to jsonl/ / a single .jsonl file."
    )


def _count_line(obj: dict) -> Tuple[int, int]:
    """Returns (1 sample, n_qa) for one parsed JSON object."""
    data = obj.get("data")
    if not isinstance(data, list):
        return 1, 0
    n_qa = sum(1 for m in data if isinstance(m, dict) and m.get("role") == "assistant")
    return 1, n_qa


def scan_jsonl_files(paths: Iterable[Path]) -> Tuple[int, int, List[Tuple[str, int, int]]]:
    total_samples = 0
    total_qa = 0
    per_file: List[Tuple[str, int, int]] = []

    for p in paths:
        s_file = 0
        q_file = 0
        with p.open(encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in {p}: {e}") from e
                s, q = _count_line(obj)
                s_file += s
                q_file += q
        total_samples += s_file
        total_qa += q_file
        per_file.append((p.name, s_file, q_file))

    return total_samples, total_qa, per_file


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        help="Training split directory (with jsonl/data_*.jsonl), or jsonl dir, or one .jsonl file",
    )
    parser.add_argument(
        "--per-file",
        action="store_true",
        help="Print per-file sample and QA counts.",
    )
    args = parser.parse_args(argv)

    root = args.path.expanduser().resolve()
    try:
        files = _resolve_jsonl_files(root)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    total_samples, total_qa, per_file = scan_jsonl_files(files)

    if args.per_file:
        print(f"{'file':<24} {'samples':>10} {'qa':>10}")
        print("-" * 48)
        for name, s, q in per_file:
            print(f"{name:<24} {s:>10} {q:>10}")
        print("-" * 48)
    print(f"samples_total: {total_samples}")
    print(f"qa_total:      {total_qa}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
