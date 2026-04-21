"""Export helpers.

Important: keep this module import-light to avoid circular imports.
Submodules such as ``openspatial_metadata.io.image_archive`` import
``openspatial_metadata.export.paths``; importing heavy modules here would
execute at package import time and can create cycles.
"""

from __future__ import annotations

from typing import Any

__all__ = ["export_metadata_to_training_bundle", "attach_task_result_as_qa_items"]


def __getattr__(name: str) -> Any:
    # Lazy re-export to keep package import side-effect-free.
    if name in __all__:
        from .run import attach_task_result_as_qa_items, export_metadata_to_training_bundle

        return {
            "export_metadata_to_training_bundle": export_metadata_to_training_bundle,
            "attach_task_result_as_qa_items": attach_task_result_as_qa_items,
        }[name]
    raise AttributeError(name)
