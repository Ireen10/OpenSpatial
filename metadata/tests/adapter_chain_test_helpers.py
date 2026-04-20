"""Test-only helpers for adapter chain tests (not part of the public package)."""

from __future__ import annotations

from typing import Any, Dict, List


class PhraseUppercaseAdapter:
    """Second-stage adapter: expects MetadataV0-shaped dict; uppercases ``objects[].phrase``."""

    def convert(self, record: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(record)
        objs: List[Any] = list(out.get("objects") or [])
        new_objs: List[Any] = []
        for o in objs:
            if not isinstance(o, dict):
                new_objs.append(o)
                continue
            d = dict(o)
            ph = d.get("phrase")
            if isinstance(ph, str) and ph:
                d["phrase"] = ph.upper()
            new_objs.append(d)
        out["objects"] = new_objs
        return out
