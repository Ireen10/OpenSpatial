from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .metadata_v0 import MetadataV0


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: Optional[str] = None


def validate_metadata_v0(_: MetadataV0) -> List[ValidationIssue]:
    """
    Minimal placeholder validator.

    v0 framework stage: keep validation lightweight; expand later as schemas stabilize.
    """
    return []

