#!/usr/bin/env python3
"""
Scan ``metadata_qa/*.jsonl`` files and print:

1. Per-QA-item counts grouped by ``task``, ``question_type``, and (when present) ``meta.qa_style``
   (e.g. ``single_axis`` / ``full_sentence`` / ``judgment`` for spatial_relation_2d).
2. Eight-way spatial direction distribution for items that reference a ``relation_id``
   present on the same metadata row: directions match
   ``openspatial_metadata.qa.spatial_relation_2d`` short tokens
   (left / right / above / below / upper left / lower left / upper right / lower right).

Each JSONL line is one ``MetadataV0``-shaped object with ``qa_items`` and ``relations``.

Usage::

    python metadata/scripts/count_metadata_qa_stats.py path/to/.../metadata_qa
    python metadata/scripts/count_metadata_qa_stats.py path/to/dataset/train_split
        # if ``metadata_qa`` exists under the split directory, it is used automatically

Runs with ``metadata/src`` on ``sys.path`` when the package is not installed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_METADATA_ROOT = Path(__file__).resolve().parents[1]
_SRC = _METADATA_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from openspatial_metadata.qa.spatial_relation_2d import SHORT_DIRECTION_ALL  # noqa: E402

# Same atom / diagonal rules as ``spatial_relation_2d._atomic_direction_for_short_answer``.
_ATOMIC_TO_AXIS = {"left": "horizontal", "right": "horizontal", "above": "vertical", "below": "vertical"}
_SHORT_DIRECTION_DIAGONAL: Dict[frozenset, str] = {
    frozenset(("left", "above")): "upper left",
    frozenset(("left", "below")): "lower left",
    frozenset(("right", "above")): "upper right",
    frozenset(("right", "below")): "lower right",
}


def _resolve_metadata_qa_dir(root: Path) -> Path:
    root = root.expanduser().resolve()
    if not root.exists():
        raise ValueError(f"Path does not exist: {root}")
    if root.is_dir() and (root / "metadata_qa").is_dir():
        return root / "metadata_qa"
    if root.is_dir() and any(root.glob("*.jsonl")):
        return root
    raise ValueError(
        f"Not a metadata_qa directory (expected *.jsonl) or split with metadata_qa/: {root}"
    )


def _sorted_jsonl_files(qa_dir: Path) -> List[Path]:
    return sorted(qa_dir.glob("*.jsonl"), key=lambda p: p.name.lower())


def _relation_eight_way(rel: Dict[str, Any]) -> Optional[str]:
    """Map a relation dict to one of eight canonical direction tokens, or None if not classifiable."""
    parts = [str(c) for c in (rel.get("components") or []) if isinstance(c, str) and c.strip()]
    if len(parts) == 1 and parts[0] in _ATOMIC_TO_AXIS:
        return parts[0]
    if len(parts) == 2:
        key = frozenset(parts)
        if key in _SHORT_DIRECTION_DIAGONAL:
            return _SHORT_DIRECTION_DIAGONAL[key]
        return None
    pred = rel.get("predicate")
    if isinstance(pred, str) and pred in _ATOMIC_TO_AXIS:
        return str(pred)
    return None


def _index_relations(relations: Any) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(relations, list):
        return out
    for rel in relations:
        if not isinstance(rel, dict):
            continue
        rid = rel.get("relation_id")
        if isinstance(rid, str) and rid:
            out[rid] = rel
    return out


def _scan_files(
    paths: Iterable[Path],
) -> tuple[int, int, Counter[str], Counter[str], Counter[str], Counter[str]]:
    """
    Returns:
        lines_with_qa, qa_total, by_task, by_question_type, by_eight_way_or_bucket,
        by_meta_qa_style (only items whose ``meta`` dict contains ``qa_style``)
    """
    lines_with_qa = 0
    qa_total = 0
    by_task: Counter[str] = Counter()
    by_question_type: Counter[str] = Counter()
    by_dir: Counter[str] = Counter()
    by_meta_qa_style: Counter[str] = Counter()

    for p in paths:
        with p.open(encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    md = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in {p}: {e}") from e
                if not isinstance(md, dict):
                    continue
                qa_items = md.get("qa_items") or []
                if not isinstance(qa_items, list) or not qa_items:
                    continue
                lines_with_qa += 1
                rel_index = _index_relations(md.get("relations"))

                for qa in qa_items:
                    if not isinstance(qa, dict):
                        continue
                    qa_total += 1
                    task = qa.get("task")
                    by_task[str(task) if task not in (None, "") else "(missing)"] += 1
                    qt = qa.get("question_type")
                    by_question_type[str(qt) if qt not in (None, "") else "(missing)"] += 1

                    meta = qa.get("meta")
                    if isinstance(meta, dict) and "qa_style" in meta:
                        st = meta.get("qa_style")
                        by_meta_qa_style[str(st) if st not in (None, "") else "(empty)"] += 1

                    rid = qa.get("relation_id")
                    if not isinstance(rid, str) or not rid:
                        by_dir["(no relation_id)"] += 1
                        continue
                    rel = rel_index.get(rid)
                    if rel is None:
                        by_dir["(relation_id not on row)"] += 1
                        continue
                    eight = _relation_eight_way(rel)
                    if eight is None:
                        by_dir["(other / non-eight-way)"] += 1
                    else:
                        by_dir[eight] += 1

    return lines_with_qa, qa_total, by_task, by_question_type, by_dir, by_meta_qa_style


def _print_counter(title: str, c: Counter[str], *, total: int) -> None:
    print(title)
    if not c:
        print("  (empty)")
        return
    for k, v in c.most_common():
        pct = (100.0 * v / total) if total else 0.0
        print(f"  {k!s:<36} {v:>8}  ({pct:5.1f}%)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        help="metadata_qa directory (*.jsonl) or split dir containing metadata_qa/",
    )
    args = parser.parse_args(argv)

    try:
        qa_dir = _resolve_metadata_qa_dir(args.path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    jsonl_files = _sorted_jsonl_files(qa_dir)
    if not jsonl_files:
        print(f"No *.jsonl files under {qa_dir}", file=sys.stderr)
        return 2

    lines_q, qa_n, by_task, by_qt, by_dir, by_style = _scan_files(jsonl_files)

    print(f"metadata_qa_dir: {qa_dir}")
    print(f"jsonl_files:     {len(jsonl_files)} file(s)")
    print(f"jsonl_lines_with_qa_items: {lines_q}")
    print(f"qa_items_total:            {qa_n}")
    print()

    _print_counter("QA counts by task", by_task, total=qa_n)
    print()
    _print_counter("QA counts by question_type", by_qt, total=qa_n)
    print()
    if by_style:
        style_total = sum(by_style.values())
        _print_counter(
            f"QA counts by meta.qa_style (only rows with meta.qa_style; n={style_total})",
            by_style,
            total=style_total,
        )
        print()

    # Fixed order for the eight canonical directions; append special buckets by frequency.
    special = {
        "(no relation_id)",
        "(relation_id not on row)",
        "(other / non-eight-way)",
    }
    ordered_dirs: List[str] = [d for d in SHORT_DIRECTION_ALL]
    extras = [k for k in by_dir if k not in ordered_dirs and k not in special]
    extras.sort(key=lambda k: (-by_dir[k], k))
    dir_keys = ordered_dirs + sorted(k for k in special if k in by_dir) + extras

    print("Eight-way direction (from qa.relation_id -> relations[] on same line)")
    for k in dir_keys:
        if k not in by_dir:
            continue
        v = by_dir[k]
        pct = (100.0 * v / qa_n) if qa_n else 0.0
        print(f"  {k!s:<36} {v:>8}  ({pct:5.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
