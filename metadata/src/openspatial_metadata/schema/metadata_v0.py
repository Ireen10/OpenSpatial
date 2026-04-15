from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DatasetV0(BaseModel):
    class Config:
        extra = "allow"

    name: str
    version: str = "v0"
    split: str = "unknown"
    source: Optional[str] = None


class ImageV0(BaseModel):
    class Config:
        extra = "allow"

    path: str
    width: Optional[int] = None
    height: Optional[int] = None
    coord_space: Optional[str] = "norm_0_999"
    coord_scale: Optional[int] = 1000


class SampleV0(BaseModel):
    class Config:
        extra = "allow"

    sample_id: str
    view_id: int = 0
    image: ImageV0


class ObjectV0(BaseModel):
    class Config:
        extra = "allow"

    object_id: str
    category: str
    phrase: Optional[str] = None
    bbox_xyxy_norm_1000: Optional[List[int]] = None
    point_uv_norm_1000: Optional[List[int]] = None
    mask_path: Optional[str] = None
    quality: Dict[str, Any] = Field(default_factory=dict)


class RelationV0(BaseModel):
    class Config:
        extra = "allow"

    anchor_id: str
    target_id: str
    predicate: str
    ref_frame: str
    components: Optional[List[str]] = None
    axis_signs: Optional[Dict[str, int]] = None
    source: Optional[str] = None
    score: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None


class MetadataV0(BaseModel):
    """
    v0 minimal skeleton aligned with wiki top-level modules.
    Extra fields are allowed to avoid over-constraining early iterations.
    """

    class Config:
        extra = "allow"

    dataset: DatasetV0
    sample: SampleV0
    camera: Optional[Dict[str, Any]] = None
    objects: List[ObjectV0] = Field(default_factory=list)
    relations: List[RelationV0] = Field(default_factory=list)
    aux: Dict[str, Any] = Field(default_factory=dict)

    # ── id helpers (v0: sample-scoped uniqueness) ──────────────────────────
    @staticmethod
    def make_object_id(category: str, index: int) -> str:
        return f"{category}#{index}"

    @staticmethod
    def make_query_id(prefix: str, index: int) -> str:
        return f"{prefix}#{index}"

