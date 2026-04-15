from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import yaml

from .schema import DatasetConfig, GlobalConfig


PathLike = Union[str, Path]


_RANGE_RE = re.compile(r"\{(\d+)\.\.(\d+)\}")


def _expand_range_pattern(pat: str) -> List[str]:
    """
    Expand patterns like 'data_{000000..000003}.jsonl' into concrete filenames.
    Only supports a single {...} range.
    """
    m = _RANGE_RE.search(pat)
    if not m:
        return [pat]
    a_raw, b_raw = m.group(1), m.group(2)
    width = max(len(a_raw), len(b_raw))
    a, b = int(a_raw), int(b_raw)
    lo, hi = (a, b) if a <= b else (b, a)
    out: List[str] = []
    for i in range(lo, hi + 1):
        token = str(i).zfill(width)
        out.append(pat[: m.start()] + token + pat[m.end() :])
    return out


def expand_inputs(inputs: Sequence[str]) -> List[str]:
    """
    Expand a list of inputs (glob strings and/or range-pattern strings) into file paths.
    """
    files: List[str] = []
    for item in inputs:
        expanded = _expand_range_pattern(item)
        for e in expanded:
            p = Path(e)
            # glob if it contains wildcard
            if any(ch in e for ch in ["*", "?", "["]):
                for gp in sorted(Path().glob(e)):
                    files.append(str(gp))
            else:
                files.append(str(p))
    # de-dup while preserving order
    seen = set()
    out = []
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        out.append(f)
    return out


@dataclass(frozen=True)
class LoadedDataset:
    config_path: str
    dataset: DatasetConfig


def load_global_config(path: Optional[PathLike]) -> GlobalConfig:
    if path is None:
        return GlobalConfig()
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return GlobalConfig.parse_obj(data)


def load_dataset_config(path: PathLike) -> DatasetConfig:
    p = Path(path)
    if p.is_dir():
        p = p / "dataset.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return DatasetConfig.parse_obj(data)


def discover_dataset_configs(config_root: PathLike) -> List[str]:
    root = Path(config_root)
    if root.is_file():
        return [str(root)]
    paths = sorted([str(p) for p in root.glob("*/dataset.yaml")])
    return paths


def resolve_adapter(dataset: DatasetConfig) -> None:
    """
    Validate that adapter spec can be imported.
    This only checks importability; it doesn't execute conversion logic.
    """
    if dataset.adapter is None:
        return
    spec = dataset.adapter
    module_name = spec.module
    class_name = spec.class_name or spec.class_
    if module_name is None and spec.file_name is not None:
        module_name = f"openspatial_metadata.adapters.{spec.file_name}"
    if module_name is None or class_name is None:
        return
    mod = importlib.import_module(module_name)
    getattr(mod, class_name)

