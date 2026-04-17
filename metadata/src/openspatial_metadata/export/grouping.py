"""Group ``AnnotationQaItemV0`` rows by visual appearance (original vs same box styling)."""

from __future__ import annotations

from typing import Any, Dict, List

from openspatial_metadata.schema.metadata_v0 import AnnotationQaItemV0


def visual_group_key(meta: Dict[str, Any]) -> str:
    """Stable key for grouping QAs that share the same visual input image."""
    n = int(meta.get("n_marked_boxes") or 0)
    if n == 0:
        return "original"
    roles = list(meta.get("marked_roles") or [])
    colors = dict(meta.get("mark_colors") or {})
    sr = ",".join(sorted(roles))
    pairs = ",".join(f"{k}:{colors[k]}" for k in sorted(colors.keys()))
    return f"{sr}#{pairs}#{n}"


def group_qa_items(qa_items: List[AnnotationQaItemV0]) -> List[List[AnnotationQaItemV0]]:
    """Preserve first-seen key order; items sharing a key sit in one list (multi-turn)."""
    buckets: Dict[str, List[AnnotationQaItemV0]] = {}
    order: List[str] = []
    for item in qa_items:
        m = dict(item.meta) if item.meta is not None else {}
        key = visual_group_key(m)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(item)
    return [buckets[k] for k in order]
