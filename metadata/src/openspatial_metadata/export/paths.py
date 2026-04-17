"""Training bundle paths inside tar: anchored at ``sample.image.path``."""

from __future__ import annotations

import hashlib
from pathlib import Path


def mark_suffix_short(visual_key: str, *, n: int = 8) -> str:
    """Short stable suffix from ``visual_group_key`` (SHA-256 hex, first ``n`` chars)."""
    h = hashlib.sha256(str(visual_key).encode("utf-8")).hexdigest()
    return h[: max(4, min(n, len(h)))]


def posix_rel_path(raw: str) -> str:
    """Normalize to POSIX relative path (no leading ``./``)."""
    p = Path(str(raw).replace("\\", "/"))
    s = p.as_posix().lstrip("./")
    return s


def training_image_relpath(
    *,
    base_image_rel: str,
    meta0: dict,
    visual_key: str,
) -> str:
    """
    ``base_image_rel``: ``MetadataV0.sample.image.path`` (as in metadata, normalized POSIX).

    - **Original** (no boxes / ``visual_key == "original"``): use **exactly** this path.
    - **Marked**: same directory + ``{stem}_m{8hex}.jpg`` where ``8hex`` is the leading bytes of
      SHA-256(``visual_key``) (re-encoded JPEG in tar).
    """
    base = posix_rel_path(base_image_rel)
    n_mark = int(meta0.get("n_marked_boxes") or 0)
    if visual_key == "original" or n_mark == 0:
        return base

    p = Path(base)
    parent = p.parent.as_posix()
    stem = p.stem
    short = mark_suffix_short(visual_key, n=8)
    name = f"{stem}_m{short}.jpg"
    if parent in ("", "."):
        return name
    return f"{parent}/{name}"


def disambiguate_relpath(rel: str, *, input_index: int, existing: set[str]) -> str:
    """
    Ensure relpath is unique within a part by adding a stable suffix when needed.

    Rule (per design):
    - keep directory structure
    - add ``__r{input_index}`` before extension
    """
    if rel not in existing:
        return rel
    p = Path(rel)
    parent = p.parent.as_posix()
    stem = p.stem
    ext = p.suffix or ""
    name = f"{stem}__r{int(input_index)}{ext}"
    if parent in ("", "."):
        cand = name
    else:
        cand = f"{parent}/{name}"
    # If still collides (pathologically), add a numeric bump.
    bump = 1
    out = cand
    while out in existing:
        name2 = f"{stem}__r{int(input_index)}_{bump}{ext}"
        out = name2 if parent in ("", ".") else f"{parent}/{name2}"
        bump += 1
    return out
