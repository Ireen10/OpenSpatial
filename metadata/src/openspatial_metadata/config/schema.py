from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import Literal


class AdapterSpec(BaseModel):
    class Config:
        extra = "forbid"
        allow_population_by_field_name = True

    file_name: Optional[str] = None
    class_name: Optional[str] = None
    module: Optional[str] = None
    class_: Optional[str] = Field(default=None, alias="class")
    # Optional constructor kwargs for the adapter class (e.g. LLM base_url, model).
    params: Optional[Dict[str, Any]] = None


class SplitSpec(BaseModel):
    class Config:
        extra = "allow"

    name: str
    input_type: Literal["jsonl", "json_files"]
    # For jsonl: list of files/globs/patterns; for json_files: one or more globs
    inputs: List[str]


class VizSpec(BaseModel):
    """Optional visualization settings (metadata viewer)."""

    class Config:
        extra = "allow"

    mode: Literal["flat"] = "flat"
    image_root: Optional[str] = None


class AdapterChainConfig(BaseModel):
    """Options for ``ChainedAdapter`` (used only when ``adapters`` has 2+ entries)."""

    class Config:
        extra = "forbid"

    # Each step must return a dict; otherwise TypeError.
    strict_dict: bool = True
    # Before running adapter at index k for every k >= N, validate current payload as MetadataV0.
    # None disables in-chain validation. Typical N=1: first adapter may ingest raw source; rest see metadata.
    validate_metadata_from_adapter_index: Optional[int] = None


class DatasetConfig(BaseModel):
    class Config:
        extra = "allow"

    name: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    adapter: Optional[AdapterSpec] = None
    # Ordered chain; when non-empty, takes precedence over legacy single `adapter`.
    adapters: Optional[List[AdapterSpec]] = None
    # Optional behavior for multi-adapter ``ChainedAdapter`` (ignored for 0–1 concrete adapters).
    adapter_chain: Optional[AdapterChainConfig] = None
    splits: List[SplitSpec]
    metadata_output_root: Optional[str] = None
    training_output_root: Optional[str] = None
    viz: Optional[VizSpec] = None


class GlobalConfig(BaseModel):
    class Config:
        extra = "allow"

    metadata_output_root: str = "metadata_out"
    # New: unified default training output root (datasets may override).
    training_output_root: Optional[str] = None
    scale: int = 1000
    batch_size: int = 1000
    num_workers: int = 0
    resume: bool = False
    strict: bool = True
    qa_config: Optional[str] = None
    # Training bundle packing (CLI export_training phase only; metadata unaffected).
    training_rows_per_part: int = 1024
    training_row_align: int = 16

