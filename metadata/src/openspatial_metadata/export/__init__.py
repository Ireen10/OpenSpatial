"""Export ``MetadataV0`` (+ ``qa_items``) to grounding-style training JSONL and image tar/tarinfo."""

from openspatial_metadata.export.run import (
    attach_task_result_as_qa_items,
    export_metadata_to_training_bundle,
)

__all__ = ["export_metadata_to_training_bundle", "attach_task_result_as_qa_items"]
