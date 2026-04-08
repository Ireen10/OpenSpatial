import numpy as np
import torch
import os
from PIL import Image

from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
from sam2.sam2_image_predictor import SAM2ImagePredictor

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from utils.data_utils import merge_overlapping_masks, merge_overlapping_boxes
from task.base_task import BaseTask


class Localizer(BaseTask):
    """Grounding DINO + SAM2 pipeline: detect objects and generate segmentation masks."""

    def __init__(self, args, device=None):
        super().__init__(args)
        grounding_model = args.get("grounding_model", "IDEA-Research/grounding-dino-tiny")
        segmenter_model = args.get("segmenter_model", "facebook/sam2-hiera-small")
        device = args.get("device") or device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.device = device

        self.processor = AutoProcessor.from_pretrained(grounding_model)
        self.detector = AutoModelForZeroShotObjectDetection.from_pretrained(grounding_model).to(device)
        self.sam2_model = SAM2ImagePredictor.from_pretrained(
            segmenter_model, trust_remote_code=True, device=device
        )
        self.output_dir = args.get("output_dir")

    def _load_image(self, img):
        """Load and convert an image input to RGB PIL Image."""
        if isinstance(img, list):
            img = img[0]
        if not isinstance(img, Image.Image):
            img = Image.open(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img

    def detect_and_segment(self, image, obj_tags):
        """Run grounding detection + SAM2 segmentation, filter and merge results.

        Args:
            image: RGB PIL Image.
            obj_tags: list of object tag strings to detect.

        Returns:
            (masks, boxes, tags) on success, or None if fewer than 2 objects found.
        """
        self.sam2_model.set_image(image)
        text_prompt = ". ".join(obj_tags)

        inputs = self.processor(images=image, text=text_prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.detector(**inputs)

        results = self.processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=0.3,
            text_threshold=0.3,
            target_sizes=[image.size[::-1]]
        )
        det_tags = results[0]["text_labels"]
        det_boxes = results[0]["boxes"].cpu().numpy()

        # Need at least 2 distinct objects
        if len(det_tags) <= 1:
            return None

        # Merge overlapping boxes with same tag
        det_boxes, det_tags = merge_overlapping_boxes(det_tags, det_boxes, overlap_threshold=0.8)

        masks, scores, _ = self.sam2_model.predict(
            point_coords=None,
            point_labels=None,
            box=det_boxes,
            multimask_output=False,
        )

        # Filter by confidence score
        keep = [i for i, score in enumerate(scores) if score >= 0.7]
        if len(keep) == 0:
            return None

        masks = masks[keep]
        det_tags = [det_tags[i] for i in keep]
        det_boxes = det_boxes[keep]

        # Merge overlapping masks with same tag
        masks, det_tags, det_boxes = merge_overlapping_masks(
            masks, det_tags, det_boxes, overlap_threshold=0.8
        )

        # Require at least 2 distinct objects after merging
        if len(det_tags) <= 1:
            return None

        return masks, det_boxes.tolist(), det_tags

    def _save_masks(self, masks, mask_dir, prefix):
        """Save binary masks as PNG files.

        Args:
            masks: array of shape (N, 1, H, W) — raw SAM2 output masks.
            mask_dir: directory to save mask images.
            prefix: filename prefix (e.g. "mask_3" or "mask_3_0").

        Returns:
            list of saved file paths.
        """
        os.makedirs(mask_dir, exist_ok=True)
        file_list = []
        for i, mask in enumerate(masks):
            binary = (mask[0] > 0).astype(np.uint8) * 255
            mask_image = Image.fromarray(binary, mode='L')
            path = os.path.join(mask_dir, f"mask_{prefix}_{i}.png")
            mask_image.save(path, format='PNG')
            file_list.append(path)
        return file_list

    def apply_transform(self, example, idx):
        """Detect and segment objects, save masks, update example fields.

        Populates:
            example["masks"]: list of mask file paths.
            example["bboxes_2d"]: list of [x1, y1, x2, y2] bounding boxes.
            example["obj_tags"]: list of detected object tag strings.
        """
        img_idx = str(idx)
        mask_dir = os.path.join(self.output_dir, self.args.get("file_name"), "masks")

        is_batched = (isinstance(example["image"], list)
                      and isinstance(example["image"][0], (list, Image.Image)))

        if is_batched:
            all_valid = True
            all_masks, all_boxes, all_tags = [], [], []
            for i, img_item in enumerate(example["image"]):
                image = self._load_image(img_item)
                tags = example["obj_tags"][i]
                result = self.detect_and_segment(image, tags)
                if result is None:
                    all_valid = False
                    all_masks.append([])
                    all_boxes.append([])
                    all_tags.append([])
                else:
                    masks, boxes, det_tags = result
                    mask_files = self._save_masks(masks, mask_dir, f"{img_idx}_{i}")
                    all_masks.append(mask_files)
                    all_boxes.append(boxes)
                    all_tags.append(det_tags)

            example["masks"] = all_masks
            example["bboxes_2d"] = all_boxes
            example["obj_tags"] = all_tags
            return example, all_valid
        else:
            image = self._load_image(example["image"])
            result = self.detect_and_segment(image, example["obj_tags"])
            if result is None:
                return example, False

            masks, boxes, det_tags = result
            mask_files = self._save_masks(masks, mask_dir, img_idx)

            assert len(mask_files) == len(boxes) == len(det_tags), (
                f"Length mismatch: {len(mask_files)} masks, "
                f"{len(boxes)} boxes, {len(det_tags)} tags."
            )

            example["masks"] = mask_files
            example["bboxes_2d"] = boxes
            example["obj_tags"] = det_tags
            return example, True
