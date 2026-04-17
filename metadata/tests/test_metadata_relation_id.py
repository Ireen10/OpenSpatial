from __future__ import annotations

import json
import unittest
from pathlib import Path

from openspatial_metadata.adapters.grounding_qa import GroundingQAAdapter
from openspatial_metadata.enrich.filters import ObjectFilterOptions
from openspatial_metadata.enrich.relation2d import enrich_relations_2d
from openspatial_metadata.schema.metadata_v0 import MetadataV0


class TestMetadataRelationId(unittest.TestCase):
    def test_parse_assigns_relation_ids_to_existing_records(self):
        sample_path = (
            Path(__file__).resolve().parent
            / ".tmp_refcoco_out"
            / "refcoco_grounding_aug_en_250618"
            / "train_small"
            / "sample_small.metadata.jsonl"
        )
        record = json.loads(sample_path.read_text(encoding="utf-8").strip().splitlines()[0])
        metadata = MetadataV0.model_validate(record)

        self.assertTrue(metadata.relations)
        self.assertTrue(all(rel.relation_id for rel in metadata.relations))
        self.assertEqual(len(metadata.relations), len({rel.relation_id for rel in metadata.relations}))

    def test_enrich_assigns_relation_ids_to_new_computed_relations(self):
        fixture = Path(__file__).resolve().parent / "fixtures" / "grounding_caption_dense_spatial.jsonl"
        record = json.loads(fixture.read_text(encoding="utf-8").strip().splitlines()[0])
        adapter = GroundingQAAdapter(
            dataset_name="refcoco_grounding_aug_en_250618",
            split="train_small",
        )
        metadata = MetadataV0.model_validate(adapter.convert(record))
        enriched = enrich_relations_2d(
            metadata,
            object_filter_options=ObjectFilterOptions(min_area_abs=0),
        )

        self.assertGreaterEqual(len(enriched.relations), 6)
        self.assertTrue(all(rel.relation_id for rel in enriched.relations))
        self.assertEqual(len(enriched.relations), len({rel.relation_id for rel in enriched.relations}))


if __name__ == "__main__":
    unittest.main()
