"""
Deduplicate objects by exact (bbox_xyxy_norm_1000, phrase) key.

Designed to run after phrase-refresh adapters (e.g. ExpressionRefreshQwenAdapter), where
`objects[].phrase` is stable and where duplicates may appear after expansion.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple


KeyMode = Literal["bbox_phrase", "bbox"]


def _dedup_key(obj: Dict[str, Any], *, key_mode: KeyMode) -> Optional[Tuple[Any, ...]]:
    bbox = obj.get("bbox_xyxy_norm_1000")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        b = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
    except (TypeError, ValueError):
        return None
    if key_mode == "bbox":
        return (b,)
    phrase = obj.get("phrase")
    if not isinstance(phrase, str) or phrase == "":
        return None
    return (b, phrase)


class ObjectDedupExactAdapter:
    """
    Remove duplicate objects when both:
    - bbox_xyxy_norm_1000 has exactly the same four values
    - phrase is exactly the same string

    Keeps the first occurrence, drops later ones. Updates queries:
    - candidate_object_ids are remapped/deduped in order
    - gold_object_id is remapped; removed if it points to a removed object
    - count is updated when present
    """

    def __init__(self, *, key_mode: KeyMode = "bbox_phrase") -> None:
        self.key_mode: KeyMode = key_mode if key_mode in ("bbox_phrase", "bbox") else "bbox_phrase"

    def convert(self, record: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = dict(record)
        objs_in = out.get("objects") or []
        if not isinstance(objs_in, list) or not objs_in:
            return out

        kept: List[Dict[str, Any]] = []
        seen: set[Tuple[Any, ...]] = set()
        oid_map: Dict[str, str] = {}
        dropped = 0

        for o in objs_in:
            if not isinstance(o, dict):
                continue
            oid = o.get("object_id")
            if not isinstance(oid, str) or not oid:
                continue
            key = _dedup_key(o, key_mode=self.key_mode)
            if key is not None and key in seen:
                dropped += 1
                continue
            if key is not None:
                seen.add(key)
            kept.append(dict(o))
            oid_map[oid] = oid

        # If object_id duplicates exist (rare), keep first and drop later by id
        uniq_kept: List[Dict[str, Any]] = []
        seen_oid: set[str] = set()
        for o in kept:
            oid = o.get("object_id")
            if isinstance(oid, str) and oid and oid not in seen_oid:
                seen_oid.add(oid)
                uniq_kept.append(o)
        kept = uniq_kept

        kept_ids = {o.get("object_id") for o in kept if isinstance(o.get("object_id"), str)}

        new_queries: List[Dict[str, Any]] = []
        for q in (out.get("queries") or []):
            if not isinstance(q, dict):
                continue
            cands = [x for x in (q.get("candidate_object_ids") or []) if isinstance(x, str) and x in kept_ids]
            # de-dup candidates while preserving order
            seen_c: set[str] = set()
            cands2: List[str] = []
            for x in cands:
                if x in seen_c:
                    continue
                seen_c.add(x)
                cands2.append(x)
            if not cands2:
                continue
            q2 = dict(q)
            q2["candidate_object_ids"] = cands2
            if "count" in q2:
                q2["count"] = len(cands2)
            had_gold = "gold_object_id" in q2
            gid = q2.get("gold_object_id")
            if isinstance(gid, str) and gid:
                if gid not in kept_ids:
                    # If previous gold was removed, fall back to first remaining candidate.
                    q2["gold_object_id"] = cands2[0]
            elif had_gold:
                # Preserve schema: if gold was present but empty/None, choose first candidate.
                q2["gold_object_id"] = cands2[0]
            elif len(cands2) == 1:
                q2["gold_object_id"] = cands2[0]
            new_queries.append(q2)

        out["objects"] = kept
        out["queries"] = new_queries
        aux = out.get("aux")
        if not isinstance(aux, dict):
            aux = {}
        aux["object_dedup_exact"] = {"dropped": dropped, "kept": len(kept)}
        out["aux"] = aux
        return out

