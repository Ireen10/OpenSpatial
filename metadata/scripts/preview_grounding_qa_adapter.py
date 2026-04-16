from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from openspatial_metadata.adapters.grounding_qa import GroundingQAAdapter
from openspatial_metadata.schema.metadata_v0 import MetadataV0


def _load_jsonl_line(path: Path, line_index: int) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if idx != line_index:
                continue
            line = line.strip()
            if not line:
                raise ValueError(f"line {line_index} is empty")
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"line {line_index} is not a JSON object")
            return obj
    raise IndexError(f"line {line_index} not found in {path}")


def _demo_record() -> Dict[str, Any]:
    # Same real example used in metadata/tests/test_adapter_grounding_qa.py
    return {
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


def main(argv: Optional[list[str]] = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--jsonl", type=str, default=None, help="Optional JSONL file to preview.")
    p.add_argument("--line", type=int, default=0, help="0-based line index in --jsonl (default: 0).")
    p.add_argument("--dataset-name", type=str, default="refcoco_grounding_aug_en_250618")
    p.add_argument("--split", type=str, default="unknown")
    p.add_argument("--no-validate", action="store_true", help="Skip MetadataV0.parse_obj validation.")
    args = p.parse_args(argv)

    if args.jsonl:
        record = _load_jsonl_line(Path(args.jsonl), args.line)
    else:
        record = _demo_record()

    adapter = GroundingQAAdapter(dataset_name=args.dataset_name, split=args.split)
    out = adapter.convert(record)

    if not args.no_validate:
        MetadataV0.parse_obj(out)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

