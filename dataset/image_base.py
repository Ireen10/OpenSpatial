import io
import json
import math
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from datasets import Dataset, load_dataset
from PIL import Image as PILImage

from utils.data_utils import flatten_annotations

HF_REPO_PATTERN = re.compile(r'^[\w-]+/[\w-]+$')


class ImageBaseDataset:
    """Base image dataset backed by parquet or HuggingFace Hub."""

    MODALITY = "image"

    def __init__(self, cfg):
        if not cfg.data_dir:
            raise ValueError("cfg.data_dir is required")
        self.cfg = cfg
        self.data_dir = cfg.data_dir
        self.data = self._load()

    # ------------------------------------------------------------------
    # Load / Override
    # ------------------------------------------------------------------

    def _load(self):
        """Load data from HuggingFace Hub or local parquet."""
        if HF_REPO_PATTERN.match(self.data_dir):
            return pd.DataFrame(load_dataset(self.data_dir, split="train"))
        return pd.read_parquet(self.data_dir, engine="pyarrow", dtype_backend="pyarrow")

    def override_data(self, data_path):
        """Replace in-memory data with another parquet file."""
        try:
            self.data = pd.read_parquet(data_path, engine="pyarrow", dtype_backend="pyarrow")
        except Exception as exc:
            raise ValueError(f"Failed to load parquet: {data_path}") from exc

    # ------------------------------------------------------------------
    # Image format conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _bytes_dict_to_pil(img_dict):
        """Convert {"bytes": ...} dict to PIL Image."""
        if isinstance(img_dict, dict) and img_dict.get("bytes"):
            try:
                return PILImage.open(io.BytesIO(img_dict["bytes"]))
            except Exception:
                return img_dict
        return img_dict

    @staticmethod
    def _pil_to_bytes_dict(image):
        """Convert PIL Image to {"bytes": ...} dict."""
        if isinstance(image, PILImage.Image):
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return {"bytes": buf.getvalue()}
        return image

    def convert_image_column_to_pil(self, df, col="image"):
        """Convert bytes dicts in a column to PIL objects (in-place)."""
        def _convert(item):
            if item is None:
                return None
            if isinstance(item, dict):
                return self._bytes_dict_to_pil(item)
            if isinstance(item, (list, tuple, np.ndarray)):
                seq = list(item)
                if seq and all(isinstance(x, dict) and "bytes" in x for x in seq):
                    return [self._bytes_dict_to_pil(x) for x in seq]
                return seq
            return item

        df[col] = [_convert(item) for item in df[col]]
        return df

    def pil_convert_to_bytes(self, df):
        """Convert PIL images in all DataFrame columns to bytes dicts."""
        def _is_pil(x):
            return isinstance(x, PILImage.Image) or (
                isinstance(x, list) and all(isinstance(i, PILImage.Image) for i in x))

        for col in df.columns:
            if df[col].apply(_is_pil).any():
                df[col] = df[col].apply(
                    lambda x: [self._pil_to_bytes_dict(i) for i in x]
                    if isinstance(x, list) else self._pil_to_bytes_dict(x))
        return df

    def pil_convert_to_np(self, data):
        """Convert image column from PIL to nested Python lists."""
        images = data["image"]
        if not len(images):
            return data

        if isinstance(images.iloc[0], list):
            data["image"] = [[np.array(img).tolist() for img in row] for row in images]
        else:
            data["image"] = [np.array(img).tolist() for img in images]
        return data

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_data(self, data_path, data=None, annotation_flag=False,
                  batch_size=1000, keep_data_columns=None):
        """Save DataFrame to parquet with optional annotation flattening."""
        if data is None:
            raise ValueError("Data to save is None")
        if not isinstance(data, pd.DataFrame):
            raise ValueError("Only pandas DataFrame is supported")

        if annotation_flag:
            keep_data_columns = keep_data_columns or [
                "messages", "QA_images", "question_tags", "question_types"]
            data = flatten_annotations(data, keep_keys=keep_data_columns)
            if len(data) > batch_size:
                self._save_batches(data_path, data, batch_size)
                return

        data.to_parquet(data_path, engine="pyarrow")

    def save_annotation_qa_metadata(
        self,
        data_path,
        data,
        *,
        batch_size=1000,
        keep_data_columns=None,
    ):
        """Persist annotation rows for QA+metadata workflows (bypasses classic ``data.parquet`` only).

        Writes:

        - ``<stem>.qa_bundle.jsonl`` — one JSON object per **input row** (sample-level QA lists,
          no image bytes) for downstream merge into ``*.metadata.jsonl``.
        - ``<stem>_flat.parquet`` — flattened one row per QA (same idea as ``annotation_flag``).

        The classic ``annotation_stage`` path is unchanged; this is used when the pipeline selects
        the ``annotation_qa_metadata_stage`` branch (or ``annotation_persist: qa_metadata``).
        """
        if data is None:
            raise ValueError("Data to save is None")
        if not isinstance(data, pd.DataFrame):
            raise ValueError("Only pandas DataFrame is supported")

        keep_data_columns = keep_data_columns or [
            "QA_images",
            "question_tags",
            "question_types",
            "question",
            "answer",
            "meta",
        ]
        present_keys = [c for c in keep_data_columns if c in data.columns]
        if not present_keys:
            raise ValueError(
                "save_annotation_qa_metadata: none of keep_data_columns are present on the DataFrame"
            )
        path = Path(data_path)
        bundle_path = path.with_name(path.stem + ".qa_bundle.jsonl")
        flat_path = path.with_name(path.stem + "_flat.parquet")

        self._write_qa_bundle_jsonl(bundle_path, data, present_keys)

        flat = flatten_annotations(data, keep_keys=present_keys)
        if len(flat) > batch_size:
            self._save_batches(str(flat_path), flat, batch_size)
        else:
            flat.to_parquet(flat_path, engine="pyarrow")

    @staticmethod
    def _write_qa_bundle_jsonl(bundle_path: Path, data: pd.DataFrame, keep_keys: list) -> None:
        """Write sample-level records; omits ``QA_images`` (bytes) and ``messages`` (unused for export)."""
        omit = {"QA_images", "messages"}
        keys = [k for k in keep_keys if k not in omit]
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        with bundle_path.open("w", encoding="utf-8") as f:
            for _, row in data.iterrows():
                record = ImageBaseDataset._row_to_qa_bundle(row, keys)
                f.write(json.dumps(record, ensure_ascii=False, default=str))
                f.write("\n")

    @staticmethod
    def _row_to_qa_bundle(row, keys: list) -> dict:
        sample = row.get("sample")
        sample_id = None
        if isinstance(sample, dict):
            sample_id = sample.get("sample_id")
        if sample_id is None:
            sample_id = row.get("sample_id")

        lengths = []
        for key in keys:
            if key not in row or row[key] is None:
                lengths.append(0)
                continue
            val = row[key]
            if isinstance(val, (list, tuple)):
                lengths.append(len(val))
            else:
                lengths.append(1)

        n = max(lengths) if lengths else 0
        qa_items = []
        for i in range(n):
            item = {}
            for key in keys:
                if key not in row or row[key] is None:
                    item[key] = None
                    continue
                val = row[key]
                if isinstance(val, (list, tuple)):
                    item[key] = val[i] if i < len(val) else None
                else:
                    item[key] = val if i == 0 else None
            qa_items.append(item)

        return {"sample_id": sample_id, "qa": qa_items}

    @staticmethod
    def _save_batches(data_path, data, batch_size):
        """Save DataFrame into multiple parquet parts."""
        base = os.path.splitext(data_path)[0]
        for i in range(math.ceil(len(data) / batch_size)):
            batch = data.iloc[i * batch_size:(i + 1) * batch_size]
            batch.to_parquet(f"{base}_part_{i}.parquet", engine="pyarrow")

    def convert_to_hf_dataset(self, data):
        """Convert pandas DataFrame to HuggingFace Dataset."""
        return Dataset.from_dict(data.to_dict(orient="list"))
