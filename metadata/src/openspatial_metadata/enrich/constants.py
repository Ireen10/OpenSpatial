"""
Thresholds calibrated at coord_scale=1000; scale at runtime with ``scale / 1000``.

See ``metadata/plans/2026-04-16_0300_metadata_next/design.md`` §4.4.
"""

from __future__ import annotations

REF_COORD_SCALE = 1000

# --- distances / deltas (same units as norm UV at REF scale) ---
MIN_ABS_DELTA_U_REF = 12
MIN_ABS_DELTA_V_REF = 12
NEAR_CENTER_DIST_REF = 16

# --- area (square of norm units at REF scale) ---
MIN_AREA_ABS_REF = 180

# --- IoU ---
AMBIGUOUS_IOU = 0.82

# --- when both |du| and |dv| >= mins: if min/max > this, drop pair (near-45°) ---
TIE_BAND_MIN_OVER_MAX_REF = 0.88

# --- aspect ratio max (w/h or h/w) for boxes ---
MAX_ASPECT_RATIO = 24.0


def scale_length(value_at_ref: float, coord_scale: int) -> float:
    return value_at_ref * (coord_scale / REF_COORD_SCALE)


def scale_area(value_at_ref: float, coord_scale: int) -> float:
    f = coord_scale / REF_COORD_SCALE
    return value_at_ref * (f * f)
