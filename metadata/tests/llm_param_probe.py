from __future__ import annotations

from typing import Any, Dict, Optional


class LlmParamProbeAdapter:
    """
    Test-only adapter: records ctor kwargs so tests can assert CLI injection behavior.
    """

    def __init__(
        self,
        *,
        base_url: str = "",
        model: str = "",
        api_key: str = "",
        timeout_s: float = 0.0,
        temperature: float = 0.0,
        max_tokens: int = 0,
        image_root: Optional[str] = None,
    ) -> None:
        self.kwargs: Dict[str, Any] = {
            "base_url": base_url,
            "model": model,
            "api_key": api_key,
            "timeout_s": timeout_s,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "image_root": image_root,
        }

    def convert(self, record: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(record)
        aux = out.get("aux")
        if not isinstance(aux, dict):
            aux = {}
        aux["llm_param_probe"] = dict(self.kwargs)
        out["aux"] = aux
        return out

