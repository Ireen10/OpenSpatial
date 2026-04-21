from __future__ import annotations

from importlib import import_module
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from openspatial_metadata.qa.runtime_stats import (
    print_and_reset_spatial_relation_2d_qa_stats,
    qa_stats_enabled,
    record_spatial_relation_2d_qa_stats,
)


@dataclass(frozen=True)
class QaTaskSpec:
    name: str
    type: str
    params: Dict[str, Any]


def load_qa_tasks_config(path: str) -> Dict[str, QaTaskSpec]:
    """
    Load the global QA task registry YAML (e.g. ``metadata/templates/configs_minimal/qa_tasks.yaml``).
    Returns mapping: task_name -> QaTaskSpec.
    """
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    tasks = data.get("tasks") or {}
    if not isinstance(tasks, dict):
        raise ValueError("qa_tasks.yaml: top-level 'tasks' must be a mapping")

    out: Dict[str, QaTaskSpec] = {}
    for name, raw in tasks.items():
        if not isinstance(raw, dict):
            continue
        if raw.get("enabled") is False:
            continue
        task_type = raw.get("type")
        params = raw.get("params") or {}
        if not isinstance(task_type, str) or not task_type:
            raise ValueError(f"qa_tasks.yaml: tasks.{name}.type must be a non-empty string")
        if not isinstance(params, dict):
            raise ValueError(f"qa_tasks.yaml: tasks.{name}.params must be a mapping")
        out[name] = QaTaskSpec(name=str(name), type=task_type, params=dict(params))
    return out


def resolve_qa_task_params(
    registry: Dict[str, QaTaskSpec],
    *,
    qa_task_name: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return merged params (defaults from registry overridden by overrides)."""
    if qa_task_name not in registry:
        raise KeyError(f"Unknown qa_task_name: {qa_task_name}")
    base = dict(registry[qa_task_name].params)
    if overrides:
        base.update(dict(overrides))
    return base


def _build_spatial_relation_2d_items(md: Any, *, params: Dict[str, Any]) -> List[Any]:
    from openspatial_metadata.qa.spatial_relation_2d import config_from_params, generate_spatial_relation_2d_qa_items

    return generate_spatial_relation_2d_qa_items(md, cfg=config_from_params(params))


def _can_build_spatial_relation_2d_items(md: Any, *, params: Dict[str, Any]) -> bool:
    objects = getattr(md, "objects", None)
    relations = getattr(md, "relations", None)
    if not objects or not relations:
        return False
    sub_tasks = params.get("sub_tasks")
    if isinstance(sub_tasks, dict):
        planned = 0
        for v in sub_tasks.values():
            try:
                planned += max(0, int(v))
            except (TypeError, ValueError):
                continue
        if planned <= 0:
            return False
    return True


def _build_items_via_convention(md: Any, *, qa_task_name: str, params: Dict[str, Any]) -> List[Any]:
    mod = import_module(f"openspatial_metadata.qa.{qa_task_name}")
    cfg_fn = getattr(mod, "config_from_params")
    gen_fn = getattr(mod, f"generate_{qa_task_name}_qa_items")
    return gen_fn(md, cfg=cfg_fn(params))


def build_qa_items(md: Any, *, qa_task_name: str, params: Dict[str, Any]) -> List[Any]:
    """
    Dispatch QA generation by task name/type. Returns a list of AnnotationQaItemV0.

    This keeps the CLI/runner generic while letting QA implementations live under ``openspatial_metadata.qa``.
    """
    spec = params  # already merged defaults+overrides
    if qa_task_name == "spatial_relation_2d" and not _can_build_spatial_relation_2d_items(md, params=spec):
        return []
    explicit_builders = {"spatial_relation_2d": _build_spatial_relation_2d_items}
    builder = explicit_builders.get(qa_task_name)
    if builder is not None:
        return builder(md, params=spec)
    try:
        return _build_items_via_convention(md, qa_task_name=qa_task_name, params=spec)
    except (ImportError, AttributeError) as exc:
        raise KeyError(f"Unsupported qa_task_name: {qa_task_name}") from exc

