from __future__ import annotations

from openspatial_metadata.adapters.object_dedup_exact import ObjectDedupExactAdapter


def test_object_dedup_exact_drops_duplicate_bbox_phrase_and_updates_queries() -> None:
    md = {
        "dataset": {"name": "d", "version": "v0", "split": "train"},
        "sample": {"sample_id": "s", "view_id": 0, "image": {"path": "a.jpg", "coord_scale": 1000}},
        "camera": None,
        "objects": [
            {"object_id": "obj#0", "category": "bear", "phrase": "sleeping bear", "bbox_xyxy_norm_1000": [1, 2, 3, 4]},
            {"object_id": "obj#1", "category": "bear", "phrase": "sleeping bear", "bbox_xyxy_norm_1000": [1, 2, 3, 4]},  # dup
            {"object_id": "obj#2", "category": "bear", "phrase": "different", "bbox_xyxy_norm_1000": [1, 2, 3, 4]},  # phrase differs
        ],
        "queries": [
            {
                "query_id": "q#0",
                "query_text": "x",
                "candidate_object_ids": ["obj#0", "obj#1", "obj#2", "obj#1"],
                "gold_object_id": "obj#1",
                "count": 4,
            }
        ],
        "relations": [],
        "qa_items": [],
        "aux": {},
    }

    out = ObjectDedupExactAdapter().convert(md)
    assert [o["object_id"] for o in out["objects"]] == ["obj#0", "obj#2"]
    q = out["queries"][0]
    assert q["candidate_object_ids"] == ["obj#0", "obj#2"]
    assert q["gold_object_id"] == "obj#0"
    assert q["count"] == 2
    assert out["aux"]["object_dedup_exact"]["dropped"] == 1


def test_object_dedup_exact_bbox_only_mode_drops_same_bbox_even_if_phrase_diff() -> None:
    md = {
        "dataset": {"name": "d", "version": "v0", "split": "train"},
        "sample": {"sample_id": "s", "view_id": 0, "image": {"path": "a.jpg", "coord_scale": 1000}},
        "camera": None,
        "objects": [
            {"object_id": "obj#0", "category": "person", "phrase": "a person", "bbox_xyxy_norm_1000": [1, 2, 3, 4]},
            {"object_id": "obj#1", "category": "person", "phrase": "someone", "bbox_xyxy_norm_1000": [1, 2, 3, 4]},  # dup bbox
            {"object_id": "obj#2", "category": "dog", "phrase": "a dog", "bbox_xyxy_norm_1000": [10, 20, 30, 40]},
        ],
        "queries": [
            {
                "query_id": "q#0",
                "query_text": "x",
                "candidate_object_ids": ["obj#1", "obj#0", "obj#2"],
                "count": 3,
            }
        ],
        "relations": [],
        "qa_items": [],
        "aux": {},
    }

    out = ObjectDedupExactAdapter(key_mode="bbox").convert(md)
    assert [o["object_id"] for o in out["objects"]] == ["obj#0", "obj#2"]
    q = out["queries"][0]
    assert q["candidate_object_ids"] == ["obj#0", "obj#2"]
    assert q["count"] == 2

