"""
Refresh ``objects[].phrase`` / ``category`` via a vision LLM (OpenAI-compatible API).

Expects ``MetadataV0``-shaped dicts (e.g. after ``GroundingQAAdapter``). Loads the image from
``image_root`` + ``sample.image.path``. For each bounding box, calls the model once; multi-object
queries are handled by iterating ``candidate_object_ids`` in order.

Model output must be a JSON object: ``{"category": "<short word>", "phrase": "<string or null>"}``.
When ``phrase`` is null (cannot describe without spatial terms), the object is **dropped** and
queries are rewritten to exclude it.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from PIL import ImageDraw

from openspatial_metadata.llm.openai_compatible import OpenAICompatibleChatClient


def _parse_json_object_from_llm_text(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    if not t:
        raise ValueError("empty model text")
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines)
    return json.loads(t)


def _image_jpeg_data_url_with_red_box(base_rgb: Image.Image, *, bbox: List[int], coord_scale: int) -> str:
    """
    Return a JPEG data URL of the image with a red rectangle drawn at bbox.
    bbox uses normalized coordinates 0..coord_scale (same convention as metadata v0).
    """
    rgb = base_rgb.copy()
    draw = ImageDraw.Draw(rgb)
    w, h = rgb.size
    sc = float(coord_scale) if coord_scale else 1000.0
    x1, y1, x2, y2 = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
    px1 = x1 / sc * w
    py1 = y1 / sc * h
    px2 = x2 / sc * w
    py2 = y2 / sc * h
    stroke = max(2, int(min(w, h) * 0.006))
    draw.rectangle([px1, py1, px2, py2], outline=(255, 0, 0), width=stroke)
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=92)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


_SYSTEM_PROMPT = (
    "You describe objects in images for grounding datasets. "
    "You must reply with a single JSON object only, no markdown fences, no extra text. "
    'Keys: "category" — one short English word in lowercase (the object type); '
    '"phrase" — a short English UNIQUE referring expression for what is inside the marked box, '
    "or null if a non-spatial description is impossible. "
    "Forbidden in phrase: any spatial/positional wording relative to the scene or image "
    "(e.g. left, right, top, bottom, above, below, behind, in front, corner, side, middle, "
    "center, next to, between, near, far from, largest, smallest, first, second). "
    "If obeying this makes description impossible, set phrase to null."
)


def _user_text_single(bbox: List[int], coord_scale: int) -> str:
    x1, y1, x2, y2 = bbox
    return (
        "The red box in the image marks the target object. "
        f"The bounding box uses normalized coordinates 0..{coord_scale} as "
        f"(x1,y1,x2,y2)=({x1},{y1},{x2},{y2}). "
        "Return a UNIQUE referring expression for the object inside the red box. "
        "Output JSON: {{\"category\": \"...\", \"phrase\": \"...\" or null}}."
    )


def _user_text_multi(
    bbox: List[int],
    coord_scale: int,
    index_1based: int,
    total: int,
) -> str:
    x1, y1, x2, y2 = bbox
    return (
        f"This image has {total} objects from the same user query; you are describing object "
        f"{index_1based} of {total} only. "
        "The red box in the image marks the target object. "
        f"The box uses normalized coordinates 0..{coord_scale} as "
        f"(x1,y1,x2,y2)=({x1},{y1},{x2},{y2}). "
        "Give a unique phrase for this instance. "
        "Output JSON: {{\"category\": \"...\", \"phrase\": \"...\" or null}}."
    )


def _messages_vision(data_url: str, user_text: str) -> List[Dict[str, Any]]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": user_text},
            ],
        },
    ]


def _normalize_llm_obj(raw: Dict[str, Any]) -> Tuple[Optional[str], str]:
    cat = raw.get("category")
    phrase = raw.get("phrase")
    if phrase is not None and not isinstance(phrase, str):
        phrase = str(phrase) if phrase is not False else None
    if isinstance(phrase, str) and not phrase.strip():
        phrase = None
    cstr = (str(cat).strip().lower() if cat is not None else "") or ""
    return phrase, cstr


class ExpressionRefreshQwenAdapter:
    def __init__(
        self,
        *,
        dataset_name: str = "unknown",
        split: str = "unknown",
        coord_space: str = "norm_0_999",
        coord_scale: int = 1000,
        image_root: Optional[str] = None,
        base_url: str = "http://127.0.0.1:8000/v1",
        model: str = "qwen3-vl-32b-instruct",
        api_key: str = "",
        timeout_s: float = 120.0,
        temperature: float = 0.2,
        max_tokens: int = 512,
        on_llm_error: str = "keep",
        print_llm_output: bool = False,
        client: Optional[OpenAICompatibleChatClient] = None,
    ) -> None:
        self.dataset_name = dataset_name
        self.split = split
        self.coord_space = coord_space
        self.coord_scale = int(coord_scale)
        self.image_root = image_root
        self.model = model
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.on_llm_error = on_llm_error if on_llm_error in ("keep", "drop") else "keep"
        self.print_llm_output = bool(print_llm_output)
        self._client = client or OpenAICompatibleChatClient(
            base_url=base_url,
            api_key=api_key,
            timeout_s=timeout_s,
        )

    def _resolve_image_path(self, record: Dict[str, Any]) -> Optional[Path]:
        sample = record.get("sample") or {}
        if not isinstance(sample, dict):
            return None
        img = sample.get("image") or {}
        if not isinstance(img, dict):
            return None
        rel = img.get("path")
        if not isinstance(rel, str) or not rel.strip():
            return None
        p = Path(rel)
        if p.is_absolute():
            return p
        if not self.image_root:
            return None
        return Path(self.image_root) / rel

    def _call_model(self, data_url: str, user_text: str) -> Dict[str, Any]:
        messages = _messages_vision(data_url, user_text)
        resp = self._client.chat_completions(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        choices = resp.get("choices") or []
        if not choices:
            raise RuntimeError("no choices in chat_completions response")
        msg = (choices[0].get("message") or {}) if isinstance(choices[0], dict) else {}
        content = msg.get("content")
        if not isinstance(content, str):
            raise RuntimeError("missing message.content string")
        parsed = _parse_json_object_from_llm_text(content)
        if self.print_llm_output:
            # Console-only debug: do not persist; may interleave with tqdm output.
            print(
                f"[openspatial-metadata][expression_refresh][llm] {parsed}",
                file=sys.stderr,
                flush=True,
            )
        return parsed

    def convert(self, record: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = dict(record)
        objects_in = out.get("objects") or []
        queries_in = out.get("queries") or []
        if not isinstance(objects_in, list) or not objects_in:
            return out

        img_path = self._resolve_image_path(out)
        aux = out.get("aux")
        if not isinstance(aux, dict):
            aux = {}
        stats: Dict[str, Any] = {
            "adapter_name": "ExpressionRefreshQwenAdapter",
            "n_llm_calls": 0,
            "errors": [],
        }

        obj_list: List[Dict[str, Any]] = [dict(o) for o in objects_in if isinstance(o, dict)]
        obj_by_id: Dict[str, Dict[str, Any]] = {}
        for o in obj_list:
            oid = o.get("object_id")
            if isinstance(oid, str) and oid:
                obj_by_id[oid] = o

        drop_ids: set[str] = set()

        if img_path is None or not img_path.is_file():
            stats["errors"].append({"code": "missing_image", "path": str(img_path) if img_path else None})
            aux["expression_refresh"] = stats
            out["aux"] = aux
            return out

        with Image.open(img_path) as im_f:
            base_rgb = im_f.convert("RGB").copy()

        def refresh_one_object(oid: str, n: int, j: int) -> None:
            obj = obj_by_id.get(oid)
            if not obj or oid in drop_ids:
                return
            bbox = obj.get("bbox_xyxy_norm_1000")
            if not isinstance(bbox, list) or len(bbox) != 4:
                stats["errors"].append({"code": "missing_bbox", "object_id": oid})
                return
            try:
                bi = j + 1
                ut = (
                    _user_text_single([int(x) for x in bbox], self.coord_scale)
                    if n == 1
                    else _user_text_multi(
                        [int(x) for x in bbox],
                        self.coord_scale,
                        index_1based=bi,
                        total=n,
                    )
                )
                data_url = _image_jpeg_data_url_with_red_box(
                    base_rgb,
                    bbox=[int(x) for x in bbox],
                    coord_scale=self.coord_scale,
                )
                raw = self._call_model(data_url, ut)
                stats["n_llm_calls"] += 1
                phrase, category = _normalize_llm_obj(raw)
                if phrase is None:
                    drop_ids.add(oid)
                else:
                    obj["phrase"] = phrase
                    if category:
                        obj["category"] = category
            except Exception as exc:  # noqa: BLE001 — aggregate per-record
                stats["errors"].append({"code": "llm_error", "object_id": oid, "detail": str(exc)})
                if self.on_llm_error == "drop":
                    drop_ids.add(oid)

        visited_oids: set[str] = set()

        # Visit each query's candidates in order; one LLM call per object.
        for q in queries_in:
            if not isinstance(q, dict):
                continue
            cands = [x for x in (q.get("candidate_object_ids") or []) if isinstance(x, str)]
            n = len(cands)
            if n == 0:
                continue
            for j, oid in enumerate(cands):
                visited_oids.add(oid)
                refresh_one_object(oid, n, j)

        # Objects not referenced by any query (edge case): refresh as single-object prompts.
        for oid, _obj in list(obj_by_id.items()):
            if oid in visited_oids:
                continue
            refresh_one_object(oid, 1, 0)

        new_objects: List[Dict[str, Any]] = []
        for o in obj_list:
            oid = o.get("object_id")
            if isinstance(oid, str) and oid in drop_ids:
                continue
            new_objects.append(o)

        kept_ids = {o.get("object_id") for o in new_objects if isinstance(o.get("object_id"), str)}

        new_queries: List[Dict[str, Any]] = []
        for q in queries_in:
            if not isinstance(q, dict):
                continue
            cands = [x for x in (q.get("candidate_object_ids") or []) if isinstance(x, str) and x in kept_ids]
            if not cands:
                continue
            q2 = dict(q)
            q2["candidate_object_ids"] = cands
            phrases: List[str] = []
            for oid in cands:
                ob = obj_by_id.get(oid)
                ph = ob.get("phrase") if ob else None
                if isinstance(ph, str) and ph.strip():
                    phrases.append(ph.strip())
            if phrases:
                q2["query_text"] = "; ".join(phrases)
            if len(cands) == 1:
                q2["gold_object_id"] = cands[0]
            else:
                q2.pop("gold_object_id", None)
            new_queries.append(q2)

        out["objects"] = new_objects
        out["queries"] = new_queries
        stats["n_objects_dropped"] = len(drop_ids)
        stats["n_objects_kept"] = len(new_objects)
        aux["expression_refresh"] = stats
        out["aux"] = aux
        return out
