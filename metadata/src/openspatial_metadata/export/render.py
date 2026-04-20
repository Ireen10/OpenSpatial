"""Render JPEG bytes from original image + QA meta + object bboxes (PIL only; no OpenCV)."""

from __future__ import annotations

import io
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw

# Align with task.annotation.core.visual_marker.COLOR_MAP (RGB tuples)
COLOR_MAP = {
    "red": (255, 0, 0),
    "blue": (0, 0, 255),
    "green": (0, 255, 0),
    "pink": (255, 192, 203),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "brown": (165, 42, 42),
}


def _bbox_norm_to_pixel_xyxy(
    bbox: List[float], width: int, height: int, *, coord_scale: float
) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = bbox
    sc = float(coord_scale) if coord_scale else 1000.0
    return (
        x0 / sc * width,
        y0 / sc * height,
        x1 / sc * width,
        y1 / sc * height,
    )


def render_group_image_jpeg(
    base: Image.Image,
    meta: Dict[str, Any],
    objects_by_id: Dict[str, Dict[str, Any]],
    *,
    coord_scale: float = 1000.0,
) -> bytes:
    """Return JPEG bytes for this group's visual: original or marked boxes."""
    n = int(meta.get("n_marked_boxes") or 0)
    if n <= 0:
        buf = io.BytesIO()
        base.convert("RGB").save(buf, format="JPEG", quality=92)
        return buf.getvalue()

    img = base.copy().convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    coord_scale = float(coord_scale) if coord_scale else 1000.0
    roles = list(meta.get("marked_roles") or [])
    colors = dict(meta.get("mark_colors") or {})
    anchor_id = meta.get("anchor_id")
    target_id = meta.get("target_id")

    for role in ("anchor", "target"):
        if role not in roles:
            continue
        oid = anchor_id if role == "anchor" else target_id
        if not isinstance(oid, str):
            continue
        obj = objects_by_id.get(oid)
        if not obj:
            continue
        bbox = obj.get("bbox_xyxy_norm_1000")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        xyxy = _bbox_norm_to_pixel_xyxy([float(x) for x in bbox], w, h, coord_scale=coord_scale)
        color_name = colors.get(role, "red")
        rgb = COLOR_MAP.get(str(color_name), (255, 0, 0))
        draw.rectangle(xyxy, outline=rgb, width=max(2, int(min(w, h) * 0.004)))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()
