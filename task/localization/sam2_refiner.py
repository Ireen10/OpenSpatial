import numpy as np
import torch
from PIL import Image
import os

from sam2.sam2_image_predictor import SAM2ImagePredictor
from task.base_task import BaseTask


class Sam2Refiner(BaseTask):
    """Refine coarse masks using SAM2 box-prompt segmentation."""

    MIN_SCORE = 0.6
    MIN_MASK_PIXELS = 20

    def __init__(self, args, device=None):
        super().__init__(args)
        segmenter_model = args.get("segmenter_model", "facebook/sam2-hiera-small")
        device = args.get("device") or device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.device = device

        self.sam2_model = SAM2ImagePredictor.from_pretrained(
            segmenter_model, trust_remote_code=True, device=device
        )

        assert "update_keys" in args, "update_keys must be specified in args."
        self.output_dir = os.path.join(self.args.get("output_dir"), self.args.get("file_name"))

    @staticmethod
    def _masks_to_bboxes(masks):
        """Compute axis-aligned bounding boxes from binary masks.

        Args:
            masks: list of 2D boolean/uint8 arrays.

        Returns:
            np.ndarray of shape (N, 4) with [x1, y1, x2, y2] per mask.
        """
        boxes = []
        for mask in masks:
            ys, xs = np.where(mask)
            if len(xs) > 0:
                boxes.append([np.min(xs), np.min(ys), np.max(xs), np.max(ys)])
            else:
                boxes.append([0, 0, 0, 0])
        return np.array(boxes)

    @staticmethod
    def _squeeze_mask(arr):
        """Squeeze (1, H, W) → (H, W) if needed."""
        return arr[0] if arr.ndim == 3 else arr

    def refine_masks(self, image, masks):
        """Re-segment each mask region using SAM2 box prompts.

        Args:
            image: RGB PIL Image.
            masks: list of 2D mask arrays (coarse masks to refine).

        Returns:
            (refined_masks, bboxes_2d, keep_indices) where keep_indices
            maps back to the original mask list. Returns ([], [], []) if
            no valid masks survive filtering.
        """
        self.sam2_model.set_image(image)
        input_boxes = self._masks_to_bboxes(masks)

        raw_masks, scores, _ = self.sam2_model.predict(
            point_coords=None,
            point_labels=None,
            box=input_boxes,
            multimask_output=False,
        )

        # Two-pass filtering: score threshold, then minimum pixel count
        refined, keep_indices = [], []
        for i, score in enumerate(scores):
            if score < self.MIN_SCORE:
                continue
            arr = self._squeeze_mask(raw_masks[i])
            if np.sum(arr) > self.MIN_MASK_PIXELS:
                refined.append(arr)
                keep_indices.append(i)

        if not keep_indices:
            return [], [], []

        bboxes_2d = self._masks_to_bboxes([m.astype(bool) for m in refined]).tolist()
        return refined, bboxes_2d, keep_indices

    def _save_masks(self, masks, mask_dir, prefix):
        """Save binary masks as grayscale PNG files.

        Args:
            masks: list of 2D arrays (values treated as boolean).
            mask_dir: output directory.
            prefix: filename prefix for saved files.

        Returns:
            list of saved file paths.
        """
        os.makedirs(mask_dir, exist_ok=True)
        file_list = []
        for i, mask in enumerate(masks):
            binary = (mask * 255).astype(np.uint8)
            img = Image.fromarray(binary, mode='L')
            path = os.path.join(mask_dir, f"example_{prefix}_box_{i}_mask.png")
            img.save(path)
            file_list.append(path)
        return file_list

    def validate_example(self, example):
        """Check that required fields exist and are non-empty."""
        for key in ("image", "masks", "obj_tags"):
            if key not in example:
                raise ValueError(f"{key} not found in example")
        if len(example["obj_tags"]) == 0:
            raise ValueError("obj_tags is empty")

    def _filter_by_keep_indices(self, example, keep_indices):
        """Keep only elements at keep_indices for each field in update_keys."""
        update_keys = self.args.get("update_keys", [])
        if not update_keys or keep_indices is None:
            return example
        for key in update_keys:
            example[key] = [example[key][i] for i in keep_indices]
        return example

    def apply_transform(self, example, idx):
        """Refine masks, filter by quality, save results.

        Populates:
            example["masks"]: list of refined mask file paths.
            example["bboxes_2d"]: list of [x1, y1, x2, y2] bounding boxes.
        """
        self.validate_example(example)

        image = Image.open(example["image"])
        if image.mode != "RGB":
            image = image.convert("RGB")

        coarse_masks = [np.array(Image.open(p)) for p in example["masks"]]
        refined_masks, bboxes_2d, keep_indices = self.refine_masks(image, coarse_masks)

        if not keep_indices:
            return None, False

        self._filter_by_keep_indices(example, keep_indices)

        mask_dir = os.path.join(self.output_dir, "masks")
        mask_files = self._save_masks(refined_masks, mask_dir, prefix=str(idx))

        assert len(mask_files) == len(example["obj_tags"]), (
            f"Mask count ({len(mask_files)}) != obj_tags count ({len(example['obj_tags'])})"
        )
        assert len(mask_files) == len(example["bboxes_3d_world_coords"]), (
            f"Mask count ({len(mask_files)}) != bboxes_3d count ({len(example['bboxes_3d_world_coords'])})"
        )

        example["masks"] = mask_files
        example["bboxes_2d"] = bboxes_2d
        return example, True
