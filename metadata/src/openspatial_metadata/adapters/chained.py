"""Compose multiple adapters: ``convert`` applies steps in order (left-to-right in config)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from openspatial_metadata.schema.metadata_v0 import MetadataV0


def _validate_metadata_v0_dict(payload: Dict[str, Any]) -> None:
    if hasattr(MetadataV0, "model_validate"):
        MetadataV0.model_validate(payload)
    else:
        MetadataV0.parse_obj(payload)


class ChainedAdapter:
    def __init__(
        self,
        steps: List[Any],
        *,
        strict_dict: bool = True,
        validate_metadata_from_adapter_index: Optional[int] = None,
    ) -> None:
        self._steps = list(steps)
        self._strict_dict = strict_dict
        v = validate_metadata_from_adapter_index
        if v is not None and v < 0:
            raise ValueError("validate_metadata_from_adapter_index must be >= 0 when set")
        self._validate_from = v

    def convert(self, record: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = dict(record)
        for i, step in enumerate(self._steps):
            v = self._validate_from
            if v is not None and i >= v:
                _validate_metadata_v0_dict(out)

            fn = getattr(step, "convert", None)
            if not callable(fn):
                continue
            prev = fn(out)
            if self._strict_dict:
                if not isinstance(prev, dict):
                    raise TypeError(
                        f"adapter chain step {i} returned {type(prev).__name__}, expected dict "
                        f"(strict_dict=True; set adapter_chain.strict_dict=false to allow passthrough)"
                    )
                out = dict(prev)
            else:
                out = dict(prev) if isinstance(prev, dict) else out
        return out
