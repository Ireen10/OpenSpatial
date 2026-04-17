from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..config.loader import discover_dataset_configs, load_dataset_config
from ..config.schema import DatasetConfig


@dataclass(frozen=True)
class DatasetIndexEntry:
    name: str
    config_path: str
    dataset: DatasetConfig


def build_dataset_index(config_root: Path) -> Dict[str, DatasetIndexEntry]:
    """
    Map ``dataset.name`` -> loaded config + yaml path.
    ``config_root`` may be a directory of ``*/dataset.yaml`` or a single ``dataset.yaml``.
    """
    paths = discover_dataset_configs(config_root)
    out: Dict[str, DatasetIndexEntry] = {}
    for p in paths:
        ds = load_dataset_config(p)
        out[ds.name] = DatasetIndexEntry(name=ds.name, config_path=str(Path(p).resolve()), dataset=ds)
    return out


def image_root_for_dataset(index: Dict[str, DatasetIndexEntry], dataset_name: str) -> Optional[str]:
    """Raw ``image_root`` string from YAML (may be relative)."""
    ent = index.get(dataset_name)
    if ent is None or ent.dataset.viz is None:
        return None
    return ent.dataset.viz.image_root


def resolved_image_root(index: Dict[str, DatasetIndexEntry], dataset_name: str) -> Optional[Path]:
    """
    Resolve ``viz.image_root`` for filesystem use.

    - If the value is an **absolute** path, use it as-is (after expanduser/resolve).
    - If **relative**, it is resolved against the directory containing the dataset
      ``dataset.yaml`` (so paths like ``../../../tests/fixtures/...`` work from the repo).
    """
    ent = index.get(dataset_name)
    if ent is None or ent.dataset.viz is None:
        return None
    raw = ent.dataset.viz.image_root
    if not raw:
        return None
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve()
    cfg_dir = Path(ent.config_path).parent
    return (cfg_dir / p).resolve()


def resolved_training_root(index: Dict[str, DatasetIndexEntry], dataset_name: str) -> Optional[Path]:
    """
    Resolve dataset.training_output_root for filesystem use.
    - absolute: resolve as-is
    - relative: resolve against current working directory (same as CLI behavior)
    """
    ent = index.get(dataset_name)
    if ent is None:
        return None
    raw = getattr(ent.dataset, "training_output_root", None)
    if not isinstance(raw, str) or not raw:
        return None
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve()
    return p.resolve()
