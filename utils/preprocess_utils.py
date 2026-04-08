"""ML image preprocessing utilities (VGGT input pipeline)."""

import torch
from torchvision import transforms as TF
from PIL import Image


def load_and_preprocess_images(image_path_list, mode="crop"):
    """Load and preprocess images for model input.

    Images are resized so dimensions are divisible by 14. Supports two modes:
    - "crop": Sets width to 518px, center crops height if needed.
    - "pad": Preserves all pixels by making the largest dimension 518px
      and padding the smaller dimension to reach a square shape.

    Args:
        image_path_list: list of image file paths.
        mode: "crop" or "pad".

    Returns:
        torch.Tensor of shape (N, 3, H, W).
    """
    if len(image_path_list) == 0:
        raise ValueError("At least 1 image is required")

    if mode not in ["crop", "pad"]:
        raise ValueError("Mode must be either 'crop' or 'pad'")

    images = []
    shapes = set()
    to_tensor = TF.ToTensor()
    target_size = 518

    for image_path in image_path_list:
        img = Image.open(image_path)
        if img.mode == "RGBA":
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(background, img)

        img = img.convert("RGB")
        width, height = img.size

        if mode == "pad":
            if width >= height:
                new_width = target_size
                new_height = round(height * (new_width / width) / 14) * 14
            else:
                new_height = target_size
                new_width = round(width * (new_height / height) / 14) * 14
        else:  # mode == "crop"
            new_width = target_size
            new_height = round(height * (new_width / width) / 14) * 14

        img = img.resize((new_width, new_height), Image.Resampling.BICUBIC)
        img = to_tensor(img)

        if mode == "crop" and new_height > target_size:
            start_y = (new_height - target_size) // 2
            img = img[:, start_y : start_y + target_size, :]

        if mode == "pad":
            h_padding = target_size - img.shape[1]
            w_padding = target_size - img.shape[2]

            if h_padding > 0 or w_padding > 0:
                pad_top = h_padding // 2
                pad_bottom = h_padding - pad_top
                pad_left = w_padding // 2
                pad_right = w_padding - pad_left

                img = torch.nn.functional.pad(
                    img, (pad_left, pad_right, pad_top, pad_bottom), mode="constant", value=1.0
                )

        shapes.add((img.shape[1], img.shape[2]))
        images.append(img)

    if len(shapes) > 1:
        print(f"Warning: Found images with different shapes: {shapes}")
        max_height = max(shape[0] for shape in shapes)
        max_width = max(shape[1] for shape in shapes)

        padded_images = []
        for img in images:
            h_padding = max_height - img.shape[1]
            w_padding = max_width - img.shape[2]

            if h_padding > 0 or w_padding > 0:
                pad_top = h_padding // 2
                pad_bottom = h_padding - pad_top
                pad_left = w_padding // 2
                pad_right = w_padding - pad_left

                img = torch.nn.functional.pad(
                    img, (pad_left, pad_right, pad_top, pad_bottom), mode="constant", value=1.0
                )
            padded_images.append(img)
        images = padded_images

    images = torch.stack(images)

    if len(image_path_list) == 1:
        if images.dim() == 3:
            images = images.unsqueeze(0)

    return images
