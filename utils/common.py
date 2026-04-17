import importlib
import os

# Maps YAML stage basename (text before the trailing "_stage") to the task subpackage under
# ``task.<subpackage>.<file_name>``. Used when a stage needs a distinct name in the pipeline
# (e.g. custom persistence) but still loads classes from ``task.annotation``.
_STAGE_SUBPACKAGE_ALIASES = {
    "annotation_qa_metadata": "annotation",
}


def resolve_task_subpackage_name(stage_name: str) -> str:
    """Resolve ``task.<name>.<file_name>`` subpackage name from a pipeline stage name.

    Convention: stage keys end with ``_stage``; the last six characters are stripped
    (see :func:`get_task_instance`).
    """
    if not stage_name.endswith("_stage"):
        return stage_name
    base = stage_name[: -len("_stage")]
    return _STAGE_SUBPACKAGE_ALIASES.get(base, base)


def get_pipeline(config):
    """Create pipeline instance from config."""
    module_path = f"pipeline.{config.pipeline.file_name}"
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, config.pipeline.class_name)
        return cls(config)
    except Exception as e:
        print(f"Failed to instantiate pipeline: {e}")
        return None


def get_task_instance(stage_name, task_cfg, cfg):
    """Create task instance from stage config."""
    sub = resolve_task_subpackage_name(stage_name)
    module_path = f"task.{sub}.{task_cfg.file_name}"
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, task_cfg.method)
        task_cfg_dict = task_cfg.__dict__.copy()
        if not task_cfg_dict.get("output_dir"):
            task_cfg_dict["output_dir"] = os.path.join(cfg.output_dir, stage_name)
        return cls(task_cfg_dict)
    except Exception as e:
        raise ImportError(f"Failed to import {module_path}.{task_cfg.method}: {e}")
