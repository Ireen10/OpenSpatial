"""Image and depth map I/O utilities."""

import io
import numpy as np
from PIL import Image


def convert_pil_to_bytes(item):
    """Convert a PIL Image (or list of Images) to PNG bytes.

    Args:
        item: PIL.Image or list of PIL.Image.

    Returns:
        bytes or list of bytes.
    """
    def _pil_to_bytes(img):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    if isinstance(item, Image.Image):
        return _pil_to_bytes(item)
    elif isinstance(item, list) and all(isinstance(i, Image.Image) for i in item):
        return [_pil_to_bytes(i) for i in item]
    return item


def load_depth_map(path, depth_scale=None):
    """Load a depth map from .npy or image file.

    Args:
        path: file path (.npy or image format).
        depth_scale: if provided, depth values are divided by this scale.

    Returns:
        np.ndarray of float64 depth values.
    """
    if path.endswith('.npy'):
        dm = np.load(path)
    else:
        dm = np.array(Image.open(path)).astype(np.float64)
    if depth_scale and depth_scale != 0:
        dm = dm / depth_scale
    return dm
