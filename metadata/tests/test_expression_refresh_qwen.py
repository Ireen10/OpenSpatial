"""Tests for ExpressionRefreshQwenAdapter with a stub OpenAI-compatible client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from openspatial_metadata.adapters.expression_refresh_qwen import ExpressionRefreshQwenAdapter
from openspatial_metadata.llm.openai_compatible import OpenAICompatibleChatClient


class _StubClient(OpenAICompatibleChatClient):
    def __init__(self, responses: List[Dict[str, Any]]) -> None:
        super().__init__(base_url="http://test/v1", api_key="", timeout_s=1.0)
        self._responses = list(responses)
        self._i = 0

    def chat_completions(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if self._i >= len(self._responses):
            raise RuntimeError("stub exhausted")
        payload = self._responses[self._i]
        self._i += 1
        text = json.dumps(payload, ensure_ascii=False)
        return {"choices": [{"message": {"content": text}}]}


def _minimal_md(
    *,
    sample_id: str = "s0",
    image_path: str = "a.jpg",
    objects: List[Dict[str, Any]],
    queries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "dataset": {"name": "d", "version": "v0", "split": "train"},
        "sample": {
            "sample_id": sample_id,
            "view_id": 0,
            "image": {"path": image_path, "width": 100, "height": 100, "coord_space": "norm_0_999", "coord_scale": 1000},
        },
        "camera": None,
        "objects": objects,
        "queries": queries,
        "relations": [],
        "aux": {},
    }


def test_single_object_updates_phrase_and_category(tmp_path: Path) -> None:
    from PIL import Image

    img = tmp_path / "a.jpg"
    Image.new("RGB", (2, 2), color=(1, 2, 3)).save(img, format="JPEG")

    stub = _StubClient([{"category": "dog", "phrase": "yellow toy"}])
    ad = ExpressionRefreshQwenAdapter(
        image_root=str(tmp_path),
        client=stub,
    )
    md = _minimal_md(
        image_path="a.jpg",
        objects=[
            {
                "object_id": "obj#0",
                "category": "",
                "phrase": "old",
                "bbox_xyxy_norm_1000": [0, 0, 100, 100],
            }
        ],
        queries=[
            {
                "query_id": "q#0",
                "query_text": "old",
                "candidate_object_ids": ["obj#0"],
                "gold_object_id": "obj#0",
            }
        ],
    )
    out = ad.convert(md)
    assert out["objects"][0]["phrase"] == "yellow toy"
    assert out["objects"][0]["category"] == "dog"
    assert out["queries"][0]["query_text"] == "yellow toy"
    assert out["aux"]["expression_refresh"]["n_llm_calls"] == 1


def test_null_phrase_drops_object_and_query(tmp_path: Path) -> None:
    from PIL import Image

    img = tmp_path / "b.jpg"
    Image.new("RGB", (2, 2), color=(9, 9, 9)).save(img, format="JPEG")

    stub = _StubClient([{"category": "x", "phrase": None}])
    ad = ExpressionRefreshQwenAdapter(image_root=str(tmp_path), client=stub)
    md = _minimal_md(
        image_path="b.jpg",
        objects=[
            {"object_id": "obj#0", "category": "", "phrase": "x", "bbox_xyxy_norm_1000": [1, 2, 3, 4]},
        ],
        queries=[
            {
                "query_id": "q#0",
                "query_text": "x",
                "candidate_object_ids": ["obj#0"],
                "gold_object_id": "obj#0",
            }
        ],
    )
    out = ad.convert(md)
    assert out["objects"] == []
    assert out["queries"] == []
    assert out["aux"]["expression_refresh"]["n_objects_dropped"] == 1


def test_multi_two_candidates_two_calls(tmp_path: Path) -> None:
    from PIL import Image

    img = tmp_path / "c.jpg"
    Image.new("RGB", (4, 4), color=(5, 5, 5)).save(img, format="JPEG")

    stub = _StubClient(
        [
            {"category": "a", "phrase": "first item"},
            {"category": "b", "phrase": "second item"},
        ]
    )
    ad = ExpressionRefreshQwenAdapter(image_root=str(tmp_path), client=stub)
    md = _minimal_md(
        image_path="c.jpg",
        objects=[
            {"object_id": "obj#0", "category": "", "phrase": "r", "bbox_xyxy_norm_1000": [0, 0, 10, 10]},
            {"object_id": "obj#1", "category": "", "phrase": "r", "bbox_xyxy_norm_1000": [20, 20, 30, 30]},
        ],
        queries=[
            {
                "query_id": "q#0",
                "query_text": "r",
                "query_type": "multi_instance_grounding",
                "candidate_object_ids": ["obj#0", "obj#1"],
                "count": 2,
            }
        ],
    )
    out = ad.convert(md)
    assert len(out["objects"]) == 2
    assert out["objects"][0]["phrase"] == "first item"
    assert out["objects"][1]["phrase"] == "second item"
    assert out["queries"][0]["query_text"] == "first item; second item"
    assert "gold_object_id" not in out["queries"][0]
    assert out["aux"]["expression_refresh"]["n_llm_calls"] == 2


def test_resolve_adapter_imports_expression_refresh() -> None:
    from openspatial_metadata.config.loader import resolve_adapter
    from openspatial_metadata.config.schema import DatasetConfig

    cfg = {
        "name": "t",
        "adapters": [
            {"file_name": "grounding_qa", "class_name": "GroundingQAAdapter"},
            {
                "file_name": "expression_refresh_qwen",
                "class_name": "ExpressionRefreshQwenAdapter",
                "params": {"base_url": "http://127.0.0.1:9/v1", "model": "m"},
            },
        ],
        "splits": [{"name": "s", "input_type": "jsonl", "inputs": ["a.jsonl"]}],
    }
    ds = DatasetConfig.parse_obj(cfg)
    resolve_adapter(ds)
