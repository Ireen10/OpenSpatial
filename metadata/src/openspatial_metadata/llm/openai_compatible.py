"""Minimal OpenAI-compatible ``/v1/chat/completions`` client (local vLLM, Ollama OpenAI bridge, etc.)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenAICompatibleChatClient:
    """
    POST ``{base_url}/chat/completions`` with JSON body
    ``{"model", "messages", ...}`` and return the parsed JSON response.

    ``base_url`` should include the ``/v1`` prefix, e.g.
    ``http://127.0.0.1:8000/v1`` so the request URL is
    ``http://127.0.0.1:8000/v1/chat/completions``.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8000/v1",
        api_key: str = "",
        timeout_s: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = float(timeout_s)

    def chat_completions(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra:
            body.update(extra)

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise RuntimeError(f"chat_completions HTTP {exc.code}: {err_body or exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"chat_completions connection failed: {exc}") from exc

        return json.loads(raw)
