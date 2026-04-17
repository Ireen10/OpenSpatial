"""
Helpers to materialize metadata + QA samples from grounding fixtures (for local inspection).

Output directory (gitignored): metadata/tests/fixtures/generated/spatial_relation_2d/
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_METADATA_SRC = REPO_ROOT / "metadata" / "src"
if str(_METADATA_SRC) not in sys.path:
    sys.path.insert(0, str(_METADATA_SRC))

from openspatial_metadata.adapters.grounding_qa import GroundingQAAdapter
from openspatial_metadata.enrich.filters import ObjectFilterOptions
from openspatial_metadata.enrich.relation2d import enrich_relations_2d
from openspatial_metadata.schema.metadata_v0 import MetadataV0
from task.annotation.spatial_relation_2d import AnnotationGenerator

FIXTURE_DIR = REPO_ROOT / "metadata" / "tests" / "fixtures"
IMAGE_ROOT = FIXTURE_DIR / "refcoco_viewer_images"
GENERATED_DIR = FIXTURE_DIR / "generated" / "spatial_relation_2d"

ENV_WRITE_ARTIFACTS = "OPENSPATIAL_WRITE_2D_RELATION_ARTIFACTS"


def load_jsonl_first_record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8").strip().splitlines()[0])


def build_metadata_from_grounding(fixture_name: str) -> MetadataV0:
    record = load_jsonl_first_record(FIXTURE_DIR / fixture_name)
    adapter = GroundingQAAdapter(
        dataset_name="refcoco_grounding_aug_en_250618",
        split="train_small",
    )
    metadata = MetadataV0.model_validate(adapter.convert(record))
    return enrich_relations_2d(
        metadata,
        object_filter_options=ObjectFilterOptions(min_area_abs=0),
    )


def write_metadata_jsonl(metadata: MetadataV0, stem: str) -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    path = GENERATED_DIR / f"{stem}.metadata.jsonl"
    line = json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False)
    path.write_text(line + "\n", encoding="utf-8")
    return path


def _qa_records_from_task_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    n = len(result["question"])
    records: List[Dict[str, Any]] = []
    for i in range(n):
        qa_img = result["QA_images"][i]
        img_len = None
        if isinstance(qa_img, dict) and isinstance(qa_img.get("bytes"), (bytes, bytearray)):
            img_len = len(qa_img["bytes"])
        records.append(
            {
                "index": i,
                "question": result["question"][i],
                "answer": result["answer"][i],
                "meta": result["meta"][i],
                "question_type": str(result["question_types"][i]),
                "question_tags": result["question_tags"][i],
                "qa_image_bytes_len": img_len,
            }
        )
    return records


def write_qa_text_artifacts(result: Dict[str, Any], stem: str) -> Tuple[Path, Path]:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    records = _qa_records_from_task_result(result)

    jsonl_path = GENERATED_DIR / f"{stem}.qa.jsonl"
    jsonl_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + ("\n" if records else ""),
        encoding="utf-8",
    )

    md_parts: List[str] = [f"# QA preview: {stem}\n"]
    for r in records:
        md_parts.append(f"## QA {r['index']}\n")
        md_parts.append(f"- **qa_style**: `{r['meta'].get('qa_style')}`\n")
        md_parts.append(f"- **relation_id**: `{r['meta'].get('relation_id')}`\n")
        if r.get("qa_image_bytes_len") is not None:
            md_parts.append(f"- **qa_image_bytes_len**: {r['qa_image_bytes_len']}\n")
        md_parts.append("\n### Question\n\n")
        md_parts.append(r["question"] + "\n\n")
        md_parts.append("### Answer\n\n")
        md_parts.append(r["answer"] + "\n\n")
        md_parts.append("### meta\n\n```json\n")
        md_parts.append(json.dumps(r["meta"], ensure_ascii=False, indent=2))
        md_parts.append("\n```\n\n")

    md_path = GENERATED_DIR / f"{stem}.qa_preview.md"
    md_path.write_text("".join(md_parts), encoding="utf-8")
    return jsonl_path, md_path


def run_task_on_metadata(
    metadata: MetadataV0,
    *,
    random_seed: int,
    sub_tasks: Dict[str, int],
    dual_box_keep_prob: float = 1.0,
) -> Tuple[Dict[str, Any], bool]:
    task = AnnotationGenerator(
        {
            "image_root": str(IMAGE_ROOT),
            "random_seed": random_seed,
            "sub_tasks": sub_tasks,
            # Tests / golden artifacts: keep all dual-box pairs. Production: set lower (e.g. 0.05–0.15).
            "dual_box_keep_prob": dual_box_keep_prob,
        }
    )
    return task.apply_transform(metadata.model_dump(), idx=0)


def write_dense_and_complex_artifacts() -> None:
    dense = build_metadata_from_grounding("grounding_caption_dense_spatial.jsonl")
    write_metadata_jsonl(dense, "dense_from_fixture")
    dense_result, dense_ok = run_task_on_metadata(
        dense,
        random_seed=7,
        sub_tasks={"single_axis": 2, "full_sentence": 2, "judgment": 2},
    )
    if dense_ok:
        write_qa_text_artifacts(dense_result, "dense_from_fixture")

    complex_md = build_metadata_from_grounding("grounding_caption_complex.jsonl")
    write_metadata_jsonl(complex_md, "complex_from_fixture")
    complex_result, complex_ok = run_task_on_metadata(
        complex_md,
        random_seed=11,
        sub_tasks={"single_axis": 2, "full_sentence": 2, "judgment": 2},
    )
    if complex_ok:
        write_qa_text_artifacts(complex_result, "complex_from_fixture")


def artifacts_enabled() -> bool:
    return os.environ.get(ENV_WRITE_ARTIFACTS, "").strip().lower() in ("1", "true", "yes", "on")


def maybe_write_artifacts_from_test() -> None:
    if not artifacts_enabled():
        return
    write_dense_and_complex_artifacts()
