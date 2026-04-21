"""
Resolve per-shard image archives and load PIL images for MetadataV0.

Used when ``sample.image.path`` refers to a member inside a ``.tar`` (same layout as
``metadata_qa/data_{shard:06d}.jsonl`` / input ``data_{shard:06d}.jsonl`` shards).
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from typing import Optional, Union

from PIL import Image

from openspatial_metadata.export.paths import posix_rel_path
from openspatial_metadata.schema.metadata_v0 import MetadataV0


def resolve_image_archive_path(pattern: str, shard_id: int, base_dir: Union[str, Path]) -> Path:
    """
    Format *pattern* with ``{shard:06d}`` (and other ``str.format`` fields if you pass them).

    Typical YAML::

        image_archive_pattern: \"archives/part_{shard:06d}.tar\"

    *shard_id* matches the 6-digit index in ``data_000042.jsonl`` (here 42).
    Relative *pattern* is resolved against *base_dir* (usually ``dataset.yaml``'s directory).
    """
    formatted = pattern.format(shard=shard_id)
    p = Path(formatted)
    if not p.is_absolute():
        p = Path(base_dir).resolve() / p
    return p.resolve()


def member_name_for_sample_image(path_in_metadata: str) -> str:
    """Normalize ``MetadataV0.sample.image.path`` for tar member lookup."""
    return posix_rel_path(path_in_metadata)


def _resolve_tar_member(tf: tarfile.TarFile, rel: str) -> tarfile.TarInfo:
    rel = member_name_for_sample_image(rel)
    candidates = [rel, rel.lstrip("./"), "./" + rel]
    for c in candidates:
        try:
            return tf.getmember(c)
        except KeyError:
            continue
    base = Path(rel).name
    for m in tf.getmembers():
        if not m.isfile():
            continue
        mn = m.name.replace("\\", "/").lstrip("./")
        if mn == rel or Path(mn).name == base:
            return m
    sample = [x.name for x in tf.getmembers() if x.isfile()][:24]
    raise FileNotFoundError(f"tar member not found: {rel!r} (sample member names: {sample})")


def load_pil_from_tar(tar_path: Union[str, Path], member_rel: str) -> Image.Image:
    """Open one member as RGB PIL; raises if missing or not readable as image."""
    with tarfile.open(tar_path, "r:*") as tf:
        m = _resolve_tar_member(tf, member_rel)
        f = tf.extractfile(m)
        if f is None:
            raise OSError(f"tar member is not a file: {member_rel!r} in {tar_path!r}")
        with f:
            data = f.read()
    im = Image.open(io.BytesIO(data))
    return im.convert("RGB")


def load_pil_for_metadata(
    md: MetadataV0,
    *,
    image_root: Optional[Union[str, Path]] = None,
    tar_path: Optional[Union[str, Path]] = None,
) -> Image.Image:
    """
    Load ``sample.image.path`` either from a directory (*image_root*) or a tar (*tar_path*).

    Exactly one of *image_root* or *tar_path* must be non-None.
    If *sample.image.path* is absolute, open that path directly (ignores *image_root*; tar still uses basename logic — prefer relative paths in metadata).
    """
    rel = md.sample.image.path
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("metadata.sample.image.path must be a non-empty string")

    p = Path(rel)
    if p.is_absolute():
        if not p.is_file():
            raise FileNotFoundError(f"image not found: {p}")
        with Image.open(p) as im_f:
            return im_f.convert("RGB").copy()

    if tar_path is not None:
        if image_root is not None:
            raise ValueError("pass only one of image_root or tar_path")
        return load_pil_from_tar(tar_path, rel).copy()

    if image_root is None:
        raise ValueError("one of image_root or tar_path is required for relative sample.image.path")

    img_path = Path(image_root) / rel
    if not img_path.is_file():
        raise FileNotFoundError(f"image not found: {img_path}")
    with Image.open(img_path) as im_f:
        return im_f.convert("RGB").copy()
