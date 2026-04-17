"""Write ``.tar`` and companion ``_tarinfo.json`` index."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Tuple


def write_tar_and_tarinfo(
    tar_path: Path,
    members: List[Tuple[str, bytes]],
) -> Dict[str, Any]:
    """
    Write a tar of ``(name, data)`` pairs and return the tarinfo dict:
    ``{ relative_path: { offset_data, size, sparse } }``.
    """
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "w") as tar:
        for name, data in members:
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))

    index: Dict[str, Any] = {}
    with tarfile.open(tar_path, "r") as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            od = getattr(m, "offset_data", None)
            if od is None:
                # Fallback: data block after POSIX ustar header (512 bytes), no GNU longname in our writes.
                od = int(m.offset) + 512
            index[m.name] = {
                "offset_data": int(od),
                "size": int(m.size),
                "sparse": None,
            }
    return index


def write_tarinfo_json(tarinfo_path: Path, index: Dict[str, Any]) -> None:
    tarinfo_path.parent.mkdir(parents=True, exist_ok=True)
    tarinfo_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
