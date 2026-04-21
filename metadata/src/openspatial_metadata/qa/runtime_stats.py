from __future__ import annotations

import json
import os
import sys
import threading
from collections import Counter, defaultdict
from typing import Dict


_QA_STATS_LOCK = threading.Lock()
_QA_STATS: Dict[str, Counter] = defaultdict(Counter)


def qa_stats_enabled() -> bool:
    v = os.environ.get("OPENSPATIAL_METADATA_QA_STATS", "")
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def record_spatial_relation_2d_qa_stats(*, sample_id: str, qa_style: str, gt_direction: str) -> None:
    if not qa_stats_enabled():
        return
    sid = str(sample_id or "unknown")
    gs = str(qa_style or "unknown")
    gd = str(gt_direction or "unknown")
    with _QA_STATS_LOCK:
        _QA_STATS["n_qa_items"]["total"] += 1
        _QA_STATS["by_sample"][sid] += 1
        _QA_STATS["by_style"][gs] += 1
        _QA_STATS["by_gt_direction"][gd] += 1


def record_spatial_relation_3d_qa_stats(*, sample_id: str, qa_style: str, gt_direction: str) -> None:
    if not qa_stats_enabled():
        return
    sid = str(sample_id or "unknown")
    gs = str(qa_style or "unknown")
    gd = str(gt_direction or "unknown")
    with _QA_STATS_LOCK:
        _QA_STATS["n_qa_items_3d"]["total"] += 1
        _QA_STATS["by_sample_3d"][sid] += 1
        _QA_STATS["by_style_3d"][gs] += 1
        _QA_STATS["by_gt_direction_3d"][gd] += 1


def print_and_reset_spatial_relation_2d_qa_stats(*, dataset: str, split: str) -> None:
    if not qa_stats_enabled():
        return
    with _QA_STATS_LOCK:
        snap = dict(_QA_STATS)
        _QA_STATS.clear()
    n_total = int((snap.get("n_qa_items") or {}).get("total", 0))
    if n_total <= 0:
        return

    by_dir = dict(snap.get("by_gt_direction") or {})
    top = sorted(by_dir.items(), key=lambda kv: (-kv[1], kv[0]))[:50]
    payload = {
        "dataset": dataset,
        "split": split,
        "n_qa_items": n_total,
        "top_gt_directions": [{"gt_direction": k, "count": int(v)} for k, v in top],
        "unique_gt_directions": int(len(by_dir)),
    }
    print(f"[openspatial-metadata][qa_stats] {json.dumps(payload, ensure_ascii=False)}", file=sys.stderr, flush=True)


def print_and_reset_spatial_relation_3d_qa_stats(*, dataset: str, split: str) -> None:
    if not qa_stats_enabled():
        return
    with _QA_STATS_LOCK:
        snap = dict(_QA_STATS)
        for k in ("n_qa_items_3d", "by_sample_3d", "by_style_3d", "by_gt_direction_3d"):
            _QA_STATS.pop(k, None)
    n_total = int((snap.get("n_qa_items_3d") or {}).get("total", 0))
    if n_total <= 0:
        return
    by_dir = dict(snap.get("by_gt_direction_3d") or {})
    top = sorted(by_dir.items(), key=lambda kv: (-kv[1], kv[0]))[:50]
    payload = {
        "dataset": dataset,
        "split": split,
        "qa_task": "spatial_relation_3d",
        "n_qa_items": n_total,
        "top_gt_directions": [{"gt_direction": k, "count": int(v)} for k, v in top],
        "unique_gt_directions": int(len(by_dir)),
    }
    print(f"[openspatial-metadata][qa_stats] {json.dumps(payload, ensure_ascii=False)}", file=sys.stderr, flush=True)
