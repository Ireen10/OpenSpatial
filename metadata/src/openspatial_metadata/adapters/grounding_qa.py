from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..schema.metadata_v0 import MetadataV0


@dataclass(frozen=True)
class _ImageInfo:
    path: str
    width: Optional[int]
    height: Optional[int]


_REF_RE = re.compile(r"<\|object_ref_start\|>(.*?)<\|object_ref_end\|>", flags=re.DOTALL)
_BOX_RE = re.compile(
    r"<\|box_start\|>\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)\s*,\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)<\|box_end\|>"
)


def _iter_messages(data: Any) -> Iterable[Dict[str, Any]]:
    if not isinstance(data, list):
        return []
    for m in data:
        if isinstance(m, dict):
            yield m


def _iter_content_items(message: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    for item in content:
        if isinstance(item, dict):
            yield item


def _extract_first_image(record: Dict[str, Any]) -> Optional[_ImageInfo]:
    for msg in _iter_messages(record.get("data")):
        for item in _iter_content_items(msg):
            if item.get("type") != "image":
                continue
            img = item.get("image")
            if not isinstance(img, dict):
                continue
            rel = img.get("relative_path")
            if not isinstance(rel, str):
                continue
            w = img.get("width")
            h = img.get("height")
            return _ImageInfo(path=rel, width=int(w) if isinstance(w, int) else None, height=int(h) if isinstance(h, int) else None)
    return None


def _extract_assistant_texts(record: Dict[str, Any]) -> List[str]:
    texts: List[str] = []
    for msg in _iter_messages(record.get("data")):
        if msg.get("role") != "assistant":
            continue
        for item in _iter_content_items(msg):
            if item.get("type") != "text":
                continue
            t = item.get("text")
            if not isinstance(t, dict):
                continue
            s = t.get("string")
            if isinstance(s, str) and s:
                texts.append(s)
    return texts


def _parse_ref_boxes(text: str) -> List[Tuple[str, List[List[int]]]]:
    """
    Return a list of (ref_exp, boxes_xyxy) parsed from one assistant text.
    Boxes are only associated to a ref when they appear after that ref and before the next ref.
    """
    out: List[Tuple[str, List[List[int]]]] = []
    refs = list(_REF_RE.finditer(text))
    if not refs:
        return out

    for idx, m in enumerate(refs):
        ref = m.group(1).strip()
        if not ref:
            continue
        start = m.end()
        end = refs[idx + 1].start() if idx + 1 < len(refs) else len(text)
        seg = text[start:end]
        boxes: List[List[int]] = []
        for bm in _BOX_RE.finditer(seg):
            x1, y1, x2, y2 = (int(bm.group(i)) for i in range(1, 5))
            boxes.append([x1, y1, x2, y2])
        if boxes:
            out.append((ref, boxes))
    return out


class GroundingQAAdapter:
    """
    Adapter for grounding-QA style multi-turn chat JSONL.
    Parses assistant grounding markers into objects + queries.
    """

    def __init__(
        self,
        *,
        dataset_name: str = "unknown",
        split: str = "unknown",
        coord_space: str = "norm_0_999",
        coord_scale: int = 1000,
        query_type_default: Optional[str] = None,
    ):
        self.dataset_name = dataset_name
        self.split = split
        self.coord_space = coord_space
        self.coord_scale = coord_scale
        self.query_type_default = query_type_default

    def convert(self, record: Dict[str, Any]) -> Dict[str, Any]:
        warnings: List[Dict[str, Any]] = []

        img = _extract_first_image(record)
        if img is None:
            warnings.append({"code": "missing_image"})
            img = _ImageInfo(path="", width=None, height=None)

        sample_id = record.get("id")
        if not isinstance(sample_id, str) or not sample_id:
            warnings.append({"code": "missing_id"})
            sample_id = "unknown"

        assistant_texts = _extract_assistant_texts(record)
        refs: List[Tuple[str, List[List[int]]]] = []
        for t in assistant_texts:
            refs.extend(_parse_ref_boxes(t))

        objects: List[Dict[str, Any]] = []
        queries: List[Dict[str, Any]] = []
        obj_idx = 0
        q_idx = 0
        parsed_boxes = 0

        for ref_exp, boxes in refs:
            cand_ids: List[str] = []
            for box in boxes:
                x1, y1, x2, y2 = box
                if x1 >= x2 or y1 >= y2:
                    warnings.append({"code": "invalid_bbox", "ref_exp": ref_exp, "bbox": box})
                    continue
                oid = MetadataV0.make_object_id("obj", obj_idx)
                obj_idx += 1
                objects.append(
                    {
                        "object_id": oid,
                        # category is required by schema, but this dataset has no explicit category.
                        "category": "",
                        "phrase": ref_exp,
                        "bbox_xyxy_norm_1000": box,
                    }
                )
                cand_ids.append(oid)
                parsed_boxes += 1

            if not cand_ids:
                continue
            qid = MetadataV0.make_query_id("q", q_idx)
            q_idx += 1
            qt = self.query_type_default or ("single_instance_grounding" if len(cand_ids) == 1 else "multi_instance_grounding")
            q: Dict[str, Any] = {
                "query_id": qid,
                "query_text": ref_exp,
                "query_type": qt,
                "candidate_object_ids": cand_ids,
                "count": len(cand_ids),
            }
            if len(cand_ids) == 1:
                q["gold_object_id"] = cand_ids[0]
            queries.append(q)

        out: Dict[str, Any] = {
            "dataset": {"name": self.dataset_name, "version": "v0", "split": self.split},
            "sample": {
                "sample_id": sample_id,
                "view_id": 0,
                "image": {
                    "path": img.path,
                    "width": img.width,
                    "height": img.height,
                    "coord_space": self.coord_space,
                    "coord_scale": self.coord_scale,
                },
            },
            "camera": None,
            "objects": objects,
            "queries": queries,
            "relations": [],
            "aux": {
                "adapter_name": "GroundingQAAdapter",
                "adapter_stats": {"n_assistant_texts": len(assistant_texts), "n_queries": len(queries), "n_objects": len(objects), "n_boxes": parsed_boxes},
                "adapter_warnings": warnings,
            },
        }
        return out

