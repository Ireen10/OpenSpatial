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
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import threading

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from openspatial_metadata.io.image_archive import load_pil_from_tar
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


def _image_jpeg_data_url(base_rgb: Image.Image) -> str:
    rgb = base_rgb.copy()
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=92)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


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


def _image_jpeg_data_url_with_boxes(
    base_rgb: Image.Image,
    *,
    bboxes: List[List[int]],
    coord_scale: int,
) -> str:
    rgb = base_rgb.copy()
    draw = ImageDraw.Draw(rgb)
    font = ImageFont.load_default()
    w, h = rgb.size
    sc = float(coord_scale) if coord_scale else 1000.0

    palette = [
        (0, 255, 0),
        (255, 0, 0),
        (0, 128, 255),
        (255, 165, 0),
        (255, 0, 255),
        (0, 255, 255),
        (255, 255, 0),
        (255, 255, 255),
    ]
    stroke = max(2, int(min(w, h) * 0.006))

    for i, bbox in enumerate(bboxes):
        x1, y1, x2, y2 = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
        px1 = x1 / sc * w
        py1 = y1 / sc * h
        px2 = x2 / sc * w
        py2 = y2 / sc * h
        color = palette[i % len(palette)]
        draw.rectangle([px1, py1, px2, py2], outline=color, width=stroke)
        # label
        label = f"#{i+1}"
        tx = max(0, int(px1) + 2)
        ty = max(0, int(py1) + 2)
        draw.text((tx, ty), label, fill=color, font=font)

    return _image_jpeg_data_url(rgb)


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


def _user_text_all_objects(*, bboxes: List[List[int]], coord_scale: int) -> str:
    lines = []
    for i, bbox in enumerate(bboxes):
        x1, y1, x2, y2 = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
        lines.append(f"- box #{i+1}: (x1,y1,x2,y2)=({x1},{y1},{x2},{y2})")
    joined = "\n".join(lines)
    return (
        "You are given ONE image with multiple bounding boxes. Each box is a DIFFERENT instance in the image, "
        "even if boxes overlap.\n"
        f"All boxes use normalized coordinates 0..{coord_scale}.\n"
        "Boxes:\n"
        f"{joined}\n\n"
        "For each box, output a UNIQUE referring expression that identifies the instance INSIDE that box.\n"
        "Rules for phrase:\n"
        "- Must be unique across the provided boxes.\n"
        "- Must NOT use spatial/positional wording (left/right/top/bottom/behind/in front/next to/between/etc.).\n"
        "- Must NOT refer to the box index or box color (e.g. '#1', 'first', 'second', 'green box', etc.).\n"
        "- If a non-spatial unique description is impossible, set phrase to null.\n\n"
        "Output JSON schema (single JSON object):\n"
        '{ "objects": [ { "index": 1, "bbox_xyxy_norm_1000": [x1,y1,x2,y2], "category": "word", "phrase": "..." or null }, ... ] }'
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


_LLM_SEM_LOCK = threading.Lock()
_LLM_SEM: Optional[threading.Semaphore] = None
_LLM_SEM_N: Optional[int] = None


def _get_global_llm_semaphore(n: int) -> threading.Semaphore:
    """
    Process-global semaphore to cap concurrent LLM requests across all adapter instances/workers.

    The first non-trivial (n>0) value wins for this process. Subsequent calls with different n will
    keep using the existing semaphore.
    """
    global _LLM_SEM, _LLM_SEM_N  # noqa: PLW0603
    n2 = max(1, int(n))
    with _LLM_SEM_LOCK:
        if _LLM_SEM is None or _LLM_SEM_N is None:
            _LLM_SEM = threading.Semaphore(n2)
            _LLM_SEM_N = n2
        return _LLM_SEM


class ExpressionRefreshQwenAdapter:
    def __init__(
        self,
        *,
        dataset_name: str = "unknown",
        split: str = "unknown",
        coord_space: str = "norm_0_999",
        coord_scale: int = 1000,
        image_root: Optional[str] = None,
        # If set (CLI: split.image_archive_pattern), load ``sample.image.path`` from this tar for the current input shard.
        image_tar_path: Optional[str] = None,
        base_url: str = "http://127.0.0.1:8000/v1",
        model: str = "qwen3-vl-32b-instruct",
        api_key: str = "",
        timeout_s: float = 120.0,
        temperature: float = 0.0,
        max_tokens: int = 512,
        on_llm_error: str = "keep",
        print_llm_output: bool = False,
        refresh_mode: str = "per_object",
        draw_boxes: bool = True,
        llm_parallelism: int = 1,
        llm_max_concurrency: int = 0,
        client: Optional[OpenAICompatibleChatClient] = None,
    ) -> None:
        self.dataset_name = dataset_name
        self.split = split
        self.coord_space = coord_space
        self.coord_scale = int(coord_scale)
        self.image_root = image_root
        self.image_tar_path = image_tar_path
        self.model = model
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.on_llm_error = on_llm_error if on_llm_error in ("keep", "drop") else "keep"
        self.print_llm_output = bool(print_llm_output)
        self.refresh_mode = refresh_mode if refresh_mode in ("per_object", "all_objects") else "per_object"
        self.draw_boxes = bool(draw_boxes)
        self.llm_parallelism = max(1, int(llm_parallelism))
        self.llm_max_concurrency = int(llm_max_concurrency)
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

        sample = out.get("sample") or {}
        img_meta = sample.get("image") or {} if isinstance(sample, dict) else {}
        rel_raw = img_meta.get("path") if isinstance(img_meta, dict) else None
        rel_str = rel_raw if isinstance(rel_raw, str) else ""

        try:
            if isinstance(rel_str, str) and rel_str.strip() and Path(rel_str).is_absolute():
                ap = Path(rel_str)
                if not ap.is_file():
                    raise FileNotFoundError(str(ap))
                with Image.open(ap) as im_f:
                    base_rgb = im_f.convert("RGB").copy()
            elif self.image_tar_path:
                if not Path(self.image_tar_path).is_file():
                    raise FileNotFoundError(self.image_tar_path)
                base_rgb = load_pil_from_tar(self.image_tar_path, rel_str).copy()
            else:
                if img_path is None or not img_path.is_file():
                    stats["errors"].append({"code": "missing_image", "path": str(img_path) if img_path else None})
                    aux["expression_refresh"] = stats
                    out["aux"] = aux
                    return out
                with Image.open(img_path) as im_f:
                    base_rgb = im_f.convert("RGB").copy()
        except OSError as exc:
            stats["errors"].append({"code": "missing_image", "path": str(exc)})
            aux["expression_refresh"] = stats
            out["aux"] = aux
            return out

        sem = _get_global_llm_semaphore(self.llm_max_concurrency) if self.llm_max_concurrency > 0 else None

        def _refresh_one_object_result(oid: str, n: int, j: int) -> Tuple[str, bool, Optional[str], str, Optional[str]]:
            """
            Returns: (object_id, called, phrase, category, error_detail)
            - called: whether an LLM request was successfully made (i.e. got a JSON object back)
            - phrase/category: normalized model output when called=True; phrase may be None
            - error_detail: non-empty when llm_error happened
            """
            obj = obj_by_id.get(oid)
            if not obj:
                return (oid, False, None, "", "missing_object")
            bbox = obj.get("bbox_xyxy_norm_1000")
            if not isinstance(bbox, list) or len(bbox) != 4:
                return (oid, False, None, "", "missing_bbox")
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
            try:
                if sem is not None:
                    sem.acquire()
                raw = self._call_model(data_url, ut)
                phrase, category = _normalize_llm_obj(raw)
                return (oid, True, phrase, category, None)
            except Exception as exc:  # noqa: BLE001
                return (oid, False, None, "", str(exc))
            finally:
                if sem is not None:
                    sem.release()

        visited_oids: set[str] = set()

        # Build refresh tasks (deduplicate by oid, keep first context n/j).
        tasks: List[Tuple[str, int, int]] = []
        for q in queries_in:
            if not isinstance(q, dict):
                continue
            cands = [x for x in (q.get("candidate_object_ids") or []) if isinstance(x, str)]
            n = len(cands)
            if n == 0:
                continue
            for j, oid in enumerate(cands):
                if oid in visited_oids:
                    continue
                visited_oids.add(oid)
                tasks.append((oid, n, j))

        for oid in list(obj_by_id.keys()):
            if oid in visited_oids:
                continue
            visited_oids.add(oid)
            tasks.append((oid, 1, 0))

        # New mode: single LLM call for all objects in this record.
        if tasks and self.refresh_mode == "all_objects":
            bboxes = []
            oids_by_index: List[str] = []
            for oid, _n, _j in tasks:
                obj = obj_by_id.get(oid) or {}
                bbox = obj.get("bbox_xyxy_norm_1000")
                if not isinstance(bbox, list) or len(bbox) != 4:
                    stats["errors"].append({"code": "missing_bbox", "object_id": oid})
                    continue
                bboxes.append([int(x) for x in bbox])
                oids_by_index.append(oid)

            if bboxes:
                user_text = _user_text_all_objects(bboxes=bboxes, coord_scale=self.coord_scale)
                raw: Dict[str, Any] = {}
                acquired = False
                try:
                    if sem is not None:
                        sem.acquire()
                        acquired = True
                    data_url = (
                        _image_jpeg_data_url_with_boxes(base_rgb, bboxes=bboxes, coord_scale=self.coord_scale)
                        if self.draw_boxes
                        else _image_jpeg_data_url(base_rgb)
                    )
                    raw = self._call_model(data_url, user_text)
                    stats["n_llm_calls"] += 1
                except Exception as exc:  # noqa: BLE001
                    stats["errors"].append({"code": "llm_error", "detail": str(exc)})
                    if self.on_llm_error == "drop":
                        drop_ids.update(oids_by_index)
                    aux["expression_refresh"] = stats
                    out["aux"] = aux
                    # continue to rewrite objects/queries according to drop_ids
                finally:
                    if sem is not None and acquired:
                        sem.release()

                objs_out = raw.get("objects") if isinstance(raw, dict) else None
                if isinstance(objs_out, list):
                    for it in objs_out:
                        if not isinstance(it, dict):
                            continue
                        idx = it.get("index")
                        if not isinstance(idx, int) or idx < 1 or idx > len(oids_by_index):
                            continue
                        oid = oids_by_index[idx - 1]
                        bbox_ret = it.get("bbox_xyxy_norm_1000")
                        if isinstance(bbox_ret, list) and len(bbox_ret) == 4:
                            exp = bboxes[idx - 1]
                            got = [int(x) for x in bbox_ret]
                            if got != exp:
                                stats["errors"].append(
                                    {"code": "bbox_mismatch", "object_id": oid, "index": idx, "expected": exp, "got": got}
                                )
                        phrase, category = _normalize_llm_obj(it)
                        if phrase is None:
                            drop_ids.add(oid)
                            continue
                        obj = obj_by_id.get(oid)
                        if obj is not None:
                            obj["phrase"] = phrase
                            if category:
                                obj["category"] = category

            # Skip per-object path; proceed to rebuild objects/queries.
            results: Dict[str, Tuple[bool, Optional[str], str, Optional[str]]] = {}
        else:
            results = {}
            if tasks and self.llm_parallelism > 1:
                mw = min(self.llm_parallelism, len(tasks))
                with ThreadPoolExecutor(max_workers=mw) as ex:
                    futs = {ex.submit(_refresh_one_object_result, oid, n, j): oid for (oid, n, j) in tasks}
                    for fut in as_completed(list(futs.keys())):
                        oid = futs[fut]
                        try:
                            (oid2, called, phrase, category, err) = fut.result()
                            results[oid2] = (called, phrase, category, err)
                        except Exception as exc:  # noqa: BLE001
                            results[oid] = (False, None, "", str(exc))
            else:
                # Sequential fallback (default behavior).
                for oid, n, j in tasks:
                    (oid2, called, phrase, category, err) = _refresh_one_object_result(oid, n, j)
                    results[oid2] = (called, phrase, category, err)

        for oid, (called, phrase, category, err) in results.items():
            if err == "missing_bbox":
                stats["errors"].append({"code": "missing_bbox", "object_id": oid})
                continue
            if err == "missing_object":
                continue
            if err:
                stats["errors"].append({"code": "llm_error", "object_id": oid, "detail": str(err)})
                if self.on_llm_error == "drop":
                    drop_ids.add(oid)
                continue
            if called:
                stats["n_llm_calls"] += 1
                if phrase is None:
                    drop_ids.add(oid)
                    continue
                obj = obj_by_id.get(oid)
                if obj is not None:
                    obj["phrase"] = phrase
                    if category:
                        obj["category"] = category

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
