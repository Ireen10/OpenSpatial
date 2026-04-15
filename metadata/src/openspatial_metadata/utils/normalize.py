from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from typing_extensions import Literal


Rounding = Literal["round"]


@dataclass(frozen=True)
class NormalizeConfig:
    width: int
    height: int
    scale: int = 1000
    rounding: Rounding = "round"
    clip: bool = True  # clamp to [0, scale)


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def pixel_to_norm_int(x: float, w: int, scale: int) -> int:
    # Team convention: round then clamp into [0, scale)
    n = int(round(x / w * scale))
    return _clamp_int(n, 0, scale - 1)


def norm_int_to_pixel(n: int, w: int, scale: int) -> int:
    # Inverse mapping (approx): round back to pixel grid
    return int(round(n / scale * w))


def point_pixel_to_norm_1000(
    xy: Sequence[float], *, width: int, height: int, scale: int = 1000
) -> List[int]:
    x, y = xy
    return [pixel_to_norm_int(x, width, scale), pixel_to_norm_int(y, height, scale)]


def bbox_xyxy_pixel_to_norm_1000(
    bbox: Sequence[float], *, width: int, height: int, scale: int = 1000
) -> List[int]:
    x1, y1, x2, y2 = bbox
    return [
        pixel_to_norm_int(x1, width, scale),
        pixel_to_norm_int(y1, height, scale),
        pixel_to_norm_int(x2, width, scale),
        pixel_to_norm_int(y2, height, scale),
    ]

