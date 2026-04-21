from __future__ import annotations

from typing import Any, Dict


def model_dump_compat(model: Any) -> Dict[str, Any]:
    """Return a dict payload for both Pydantic v1/v2 models."""
    if hasattr(model, "model_dump"):
        data = model.model_dump()
    else:
        data = model.dict()
    return dict(data) if isinstance(data, dict) else {}


def model_validate_compat(model_cls: Any, payload: Any) -> Any:
    """Validate payload via model class across Pydantic v1/v2."""
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(payload)
    return model_cls.parse_obj(payload)


def model_copy_update_compat(model: Any, *, update: Dict[str, Any]) -> Any:
    """Return a copied model with field updates across Pydantic v1/v2."""
    if hasattr(model, "model_copy"):
        return model.model_copy(update=update)
    return model.copy(update=update)
