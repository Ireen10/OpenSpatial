"""Multi-adapter chain: ChainedAdapter + dataset config precedence."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from openspatial_metadata.adapters.chained import ChainedAdapter
from openspatial_metadata.adapters.grounding_qa import GroundingQAAdapter
from openspatial_metadata.config.loader import adapter_specs_for_dataset, load_dataset_config, resolve_adapter
from openspatial_metadata.config.schema import DatasetConfig

from adapter_chain_test_helpers import PhraseUppercaseAdapter


class _AddKey:
    def __init__(self, key: str, value: object) -> None:
        self._key = key
        self._value = value

    def convert(self, record: dict) -> dict:
        d = dict(record)
        d[self._key] = self._value
        return d


class _Identity:
    def convert(self, record: dict) -> dict:
        return dict(record)


class _BadReturn:
    def convert(self, record: dict) -> object:
        return "not-a-dict"


def _minimal_valid_metadata_dict() -> dict:
    return {
        "dataset": {"name": "demo", "version": "v0", "split": "train"},
        "sample": {
            "sample_id": "demo/0",
            "view_id": 0,
            "image": {"path": "a.png", "width": 1, "height": 1},
        },
        "camera": None,
        "objects": [{"object_id": "chair#0", "category": "chair"}],
        "relations": [],
        "aux": {},
    }


def test_chained_adapter_applies_in_order() -> None:
    chain = ChainedAdapter([_AddKey("a", 1), _AddKey("b", 2)])
    out = chain.convert({"x": 0})
    assert out == {"x": 0, "a": 1, "b": 2}


def test_adapter_specs_non_empty_adapters_wins() -> None:
    cfg = {
        "name": "t",
        "adapter": {"file_name": "passthrough", "class_name": "PassthroughAdapter"},
        "adapters": [
            {"file_name": "passthrough", "class_name": "PassthroughAdapter"},
            {"file_name": "passthrough", "class_name": "PassthroughAdapter"},
        ],
        "splits": [{"name": "s", "input_type": "jsonl", "inputs": ["a.jsonl"]}],
    }
    ds = load_dataset_config_from_dict(cfg)
    specs = adapter_specs_for_dataset(ds)
    assert len(specs) == 2


def test_adapter_specs_empty_adapters_falls_back_to_single_adapter() -> None:
    cfg = {
        "name": "t",
        "adapter": {"file_name": "passthrough", "class_name": "PassthroughAdapter"},
        "adapters": [],
        "splits": [{"name": "s", "input_type": "jsonl", "inputs": ["a.jsonl"]}],
    }
    ds = load_dataset_config_from_dict(cfg)
    specs = adapter_specs_for_dataset(ds)
    assert len(specs) == 1


def test_resolve_adapter_imports_all_chain_members() -> None:
    cfg = {
        "name": "t",
        "adapters": [
            {"file_name": "grounding_qa", "class_name": "GroundingQAAdapter"},
            {"file_name": "passthrough", "class_name": "PassthroughAdapter"},
        ],
        "splits": [{"name": "s", "input_type": "jsonl", "inputs": ["a.jsonl"]}],
    }
    ds = load_dataset_config_from_dict(cfg)
    resolve_adapter(ds)


def test_grounding_qa_then_phrase_uppercase_chain() -> None:
    """Real ingestion adapter + metadata mutator; second step uppercases object phrases."""
    record = {
        "meta_prompt": [""],
        "data": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "image": {
                            "type": "relative_path",
                            "format": "image/jpeg",
                            "relative_path": "type7/train2014/COCO_train2014_000000569667.jpg",
                            "width": 640,
                            "height": 426,
                        },
                    },
                    {
                        "type": "text",
                        "text": {
                            "type": "string",
                            "format": "utf-8",
                            "string": "Please provide the bounding box coordinate of the region this sentence describes: yeah impossible here the one with yellow cheese on end",
                        },
                    },
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": {
                            "type": "string",
                            "format": "utf-8",
                            "string": "<|object_ref_start|>yeah impossible here the one with yellow cheese on end<|object_ref_end|><|box_start|>(601,346),(953,828)<|box_end|>",
                        },
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": {
                            "type": "string",
                            "format": "utf-8",
                            "string": "Please provide the bounding box coordinate of the region this sentence describes: darkest hot dog",
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": {
                            "type": "string",
                            "format": "utf-8",
                            "string": "<|object_ref_start|>darkest hot dog<|object_ref_end|><|box_start|>(023,191),(353,636)<|box_end|>",
                        },
                    }
                ],
            },
        ],
        "repeat_flag": 1,
        "id": "type7-0806-6_myNGTNg5_2690",
    }
    g = GroundingQAAdapter(dataset_name="refcoco_grounding_aug_en_250618", split="train")
    chain = ChainedAdapter(
        [g, PhraseUppercaseAdapter()],
        validate_metadata_from_adapter_index=1,
    )
    out = chain.convert(record)
    assert len(out["objects"]) == 2
    assert out["objects"][0]["phrase"] == "YEAH IMPOSSIBLE HERE THE ONE WITH YELLOW CHEESE ON END"
    assert out["objects"][1]["phrase"] == "DARKEST HOT DOG"


def test_yaml_file_with_adapters_list(tmp_path: Path) -> None:
    p = tmp_path / "dataset.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "name": "chain_ds",
                "adapters": [
                    {"file_name": "passthrough", "class_name": "PassthroughAdapter"},
                ],
                "splits": [{"name": "s", "input_type": "jsonl", "inputs": ["a.jsonl"]}],
            }
        ),
        encoding="utf-8",
    )
    ds = load_dataset_config(p)
    assert len(adapter_specs_for_dataset(ds)) == 1
    resolve_adapter(ds)


def load_dataset_config_from_dict(cfg: dict) -> DatasetConfig:
    return DatasetConfig.parse_obj(cfg)


def test_chained_adapter_strict_dict_rejects_non_dict() -> None:
    with pytest.raises(TypeError):
        ChainedAdapter([_AddKey("a", 1), _BadReturn()], strict_dict=True).convert({"x": 0})


def test_chained_adapter_validate_metadata_from_second_step() -> None:
    md = _minimal_valid_metadata_dict()
    chain = ChainedAdapter(
        [_Identity(), _AddKey("tag", "ok")],
        validate_metadata_from_adapter_index=1,
    )
    out = chain.convert(md)
    assert out["tag"] == "ok"


def test_chained_adapter_validate_metadata_raises_on_invalid_intermediate() -> None:
    chain = ChainedAdapter(
        [_AddKey("noise", 1), _Identity()],
        validate_metadata_from_adapter_index=1,
    )
    with pytest.raises(Exception):
        chain.convert({"not": "metadata"})


def test_dataset_config_adapter_chain_fields() -> None:
    cfg = {
        "name": "t",
        "adapters": [
            {"file_name": "grounding_qa", "class_name": "GroundingQAAdapter"},
            {"file_name": "passthrough", "class_name": "PassthroughAdapter"},
        ],
        "adapter_chain": {
            "strict_dict": True,
            "validate_metadata_from_adapter_index": 1,
        },
        "splits": [{"name": "s", "input_type": "jsonl", "inputs": ["a.jsonl"]}],
    }
    ds = load_dataset_config_from_dict(cfg)
    assert ds.adapter_chain is not None
    assert ds.adapter_chain.strict_dict is True
    assert ds.adapter_chain.validate_metadata_from_adapter_index == 1
