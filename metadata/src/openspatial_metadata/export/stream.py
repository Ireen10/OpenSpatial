"""Streaming writer for training bundles (append tar/jsonl; write tarinfo at end)."""

from __future__ import annotations

import io
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class TrainingBundlePaths:
    images_dir: Path
    jsonl_dir: Path
    tar_path: Path
    tarinfo_path: Path
    jsonl_path: Path


def bundle_paths(output_root: Path, bundle_id: int) -> TrainingBundlePaths:
    """Training bundle files: ``data_{bundle_id:06d}.tar`` (+ tarinfo, jsonl)."""
    images_dir = output_root / "images"
    jsonl_dir = output_root / "jsonl"
    images_dir.mkdir(parents=True, exist_ok=True)
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    return TrainingBundlePaths(
        images_dir=images_dir,
        jsonl_dir=jsonl_dir,
        tar_path=images_dir / f"data_{bundle_id:06d}.tar",
        tarinfo_path=images_dir / f"data_{bundle_id:06d}_tarinfo.json",
        jsonl_path=jsonl_dir / f"data_{bundle_id:06d}.jsonl",
    )


class TrainingBundleWriter:
    """
    Appendable writer:
    - tar: append members
    - jsonl: append lines
    - tarinfo: recomputed from tar at finalize()
    """

    def __init__(self, paths: TrainingBundlePaths, *, resume: bool):
        self.paths = paths
        self.resume = resume
        self._tar: Optional[tarfile.TarFile] = None
        self._jsonl_f = None
        self._names: Set[str] = set()

    def __enter__(self) -> "TrainingBundleWriter":
        mode = "a" if self.resume and self.paths.tar_path.exists() else "w"
        self._tar = tarfile.open(self.paths.tar_path, mode)
        if self.resume and self.paths.tar_path.exists():
            try:
                # capture existing names for collision avoidance
                with tarfile.open(self.paths.tar_path, "r") as t:
                    self._names = {m.name for m in t.getmembers() if m.isfile()}
            except Exception:
                self._names = set()
        self._jsonl_f = self.paths.jsonl_path.open("a" if (self.resume and self.paths.jsonl_path.exists()) else "w", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._jsonl_f is not None:
                self._jsonl_f.flush()
                self._jsonl_f.close()
        finally:
            if self._tar is not None:
                self._tar.close()

    @property
    def existing_names(self) -> Set[str]:
        return self._names

    def add_image(self, name: str, data: bytes) -> None:
        assert self._tar is not None
        ti = tarfile.TarInfo(name=name)
        ti.size = len(data)
        self._tar.addfile(ti, io.BytesIO(data))
        self._names.add(name)

    def add_jsonl_row(self, row: Dict[str, Any]) -> None:
        assert self._jsonl_f is not None
        self._jsonl_f.write(json.dumps(row, ensure_ascii=False))
        self._jsonl_f.write("\n")

    def finalize_tarinfo(self) -> Dict[str, Any]:
        """
        Recompute tarinfo index for all members and write json.
        """
        # Ensure all bytes are flushed to disk before reading tar back.
        if self._tar is not None:
            try:
                self._tar.close()
            finally:
                self._tar = None
        index: Dict[str, Any] = {}
        with tarfile.open(self.paths.tar_path, "r") as tar:
            for m in tar.getmembers():
                if not m.isfile():
                    continue
                od = getattr(m, "offset_data", None)
                if od is None:
                    od = int(m.offset) + 512
                index[m.name] = {"offset_data": int(od), "size": int(m.size), "sparse": None}
        self.paths.tarinfo_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        return index

