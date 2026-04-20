"""Tests for ExpressionRefreshQwenAdapter with a stub OpenAI-compatible client."""

from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any, Dict, List

from openspatial_metadata.adapters.expression_refresh_qwen import ExpressionRefreshQwenAdapter
from openspatial_metadata.llm.openai_compatible import OpenAICompatibleChatClient


class _StubClient(OpenAICompatibleChatClient):
    def __init__(self, responses: List[Dict[str, Any]]) -> None:
        super().__init__(base_url="http://test/v1", api_key="", timeout_s=1.0)
        self._responses = list(responses)
        self._i = 0
        self.last_messages: List[Dict[str, Any]] | None = None

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
        self.last_messages = messages
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
    assert stub.last_messages is not None
    user_content = stub.last_messages[1]["content"]
    assert isinstance(user_content, list)
    assert user_content[0]["type"] == "image_url"
    assert user_content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert user_content[1]["type"] == "text"
    assert "red box" in user_content[1]["text"].lower()
    assert "unique" in user_content[1]["text"].lower()


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
    assert stub.last_messages is not None
    user_content = stub.last_messages[1]["content"]
    assert isinstance(user_content, list)
    assert "red box" in user_content[1]["text"].lower()


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
    assert stub.last_messages is not None
    user_content = stub.last_messages[1]["content"]
    assert isinstance(user_content, list)
    assert user_content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "red box" in user_content[1]["text"].lower()
    assert "unique" in user_content[1]["text"].lower()


def test_all_objects_mode_single_call_updates_both_and_rewrites_query(tmp_path: Path) -> None:
    from PIL import Image

    img = tmp_path / "m.jpg"
    Image.new("RGB", (6, 6), color=(3, 3, 3)).save(img, format="JPEG")

    stub = _StubClient(
        [
            {
                "objects": [
                    {
                        "index": 1,
                        "bbox_xyxy_norm_1000": [0, 0, 10, 10],
                        "category": "person",
                        "phrase": "woman wearing glasses",
                    },
                    {
                        "index": 2,
                        "bbox_xyxy_norm_1000": [20, 20, 30, 30],
                        "category": "person",
                        "phrase": "man in a blue shirt",
                    },
                ]
            }
        ]
    )
    ad = ExpressionRefreshQwenAdapter(
        image_root=str(tmp_path),
        client=stub,
        refresh_mode="all_objects",
        draw_boxes=False,
    )
    md = _minimal_md(
        image_path="m.jpg",
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
    assert out["aux"]["expression_refresh"]["n_llm_calls"] == 1
    assert out["objects"][0]["phrase"] == "woman wearing glasses"
    assert out["objects"][0]["category"] == "person"
    assert out["objects"][1]["phrase"] == "man in a blue shirt"
    assert out["queries"][0]["query_text"] == "woman wearing glasses; man in a blue shirt"
    assert stub.last_messages is not None
    user_text = stub.last_messages[1]["content"][1]["text"].lower()
    assert "different instance" in user_text
    assert "boxes:" in user_text


def test_all_objects_mode_bbox_mismatch_is_recorded(tmp_path: Path) -> None:
    from PIL import Image

    img = tmp_path / "mm.jpg"
    Image.new("RGB", (6, 6), color=(3, 3, 3)).save(img, format="JPEG")

    stub = _StubClient(
        [
            {
                "objects": [
                    {
                        "index": 1,
                        "bbox_xyxy_norm_1000": [999, 999, 999, 999],  # mismatch
                        "category": "person",
                        "phrase": "woman wearing glasses",
                    }
                ]
            }
        ]
    )
    ad = ExpressionRefreshQwenAdapter(
        image_root=str(tmp_path),
        client=stub,
        refresh_mode="all_objects",
        draw_boxes=False,
    )
    md = _minimal_md(
        image_path="mm.jpg",
        objects=[
            {"object_id": "obj#0", "category": "", "phrase": "r", "bbox_xyxy_norm_1000": [0, 0, 10, 10]},
        ],
        queries=[
            {"query_id": "q#0", "query_text": "r", "candidate_object_ids": ["obj#0"], "gold_object_id": "obj#0"}
        ],
    )
    out = ad.convert(md)
    errs = out["aux"]["expression_refresh"]["errors"]
    assert any(e.get("code") == "bbox_mismatch" for e in errs)


def test_multi_two_candidates_can_run_in_parallel_with_limit(tmp_path: Path) -> None:
    from PIL import Image

    img = tmp_path / "p.jpg"
    Image.new("RGB", (8, 8), color=(7, 7, 7)).save(img, format="JPEG")

    class _BlockingStub(OpenAICompatibleChatClient):
        def __init__(self) -> None:
            super().__init__(base_url="http://test/v1", api_key="", timeout_s=1.0)
            self._lock = threading.Lock()
            self.active = 0
            self.max_active = 0
            self.ready2 = threading.Event()
            self.release = threading.Event()

        def chat_completions(
            self,
            *,
            model: str,
            messages: List[Dict[str, Any]],
            temperature: float = 0.0,
            max_tokens: int = 512,
            extra: Dict[str, Any] | None = None,
        ) -> Dict[str, Any]:
            with self._lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                if self.active >= 2:
                    self.ready2.set()
            # Wait until both calls have started.
            self.ready2.wait(timeout=2.0)
            # Block until test releases both.
            self.release.wait(timeout=2.0)
            with self._lock:
                self.active -= 1

            user_text = messages[1]["content"][1]["text"]
            # Return phrase based on bbox x1 to make mapping deterministic regardless of call order.
            phrase = "first item" if "(x1,y1,x2,y2)=(0," in user_text else "second item"
            payload = {"category": "x", "phrase": phrase}
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    stub = _BlockingStub()
    ad = ExpressionRefreshQwenAdapter(
        image_root=str(tmp_path),
        client=stub,
        llm_parallelism=2,
        llm_max_concurrency=2,
    )
    md = _minimal_md(
        image_path="p.jpg",
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

    t = threading.Thread(target=lambda: ad.convert(md), daemon=True)
    t.start()
    assert stub.ready2.wait(timeout=2.0)
    stub.release.set()
    t.join(timeout=2.0)
    assert stub.max_active >= 2


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
