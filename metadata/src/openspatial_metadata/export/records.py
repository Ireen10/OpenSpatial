"""Build grounding-style JSON objects (meta_prompt / data / id)."""

from __future__ import annotations

from typing import Any, Dict, List

from openspatial_metadata.schema.metadata_v0 import AnnotationQaItemV0


def _text_part(text: str) -> Dict[str, Any]:
    return {
        "type": "text",
        "text": {
            "type": "string",
            "format": "utf-8",
            "string": text,
        },
    }


def _image_part(relative_path: str, width: int, height: int) -> Dict[str, Any]:
    return {
        "type": "image",
        "image": {
            "type": "relative_path",
            "format": "image/jpeg",
            "relative_path": relative_path,
            "width": int(width),
            "height": int(height),
        },
    }


def build_training_line(
    group: List[AnnotationQaItemV0],
    *,
    relative_path: str,
    image_width: int,
    image_height: int,
    record_id: str = "",
) -> Dict[str, Any]:
    """One training JSON object: first user turn has image + first question; then assistants; alternate."""
    data: List[Dict[str, Any]] = []
    for i, item in enumerate(group):
        if i == 0:
            data.append(
                {
                    "role": "user",
                    "content": [
                        _image_part(relative_path, image_width, image_height),
                        _text_part(item.question),
                    ],
                }
            )
        else:
            data.append({"role": "user", "content": [_text_part(item.question)]})
        data.append({"role": "assistant", "content": [_text_part(item.answer)]})

    return {
        "meta_prompt": [""],
        "data": data,
        "id": record_id,
    }
