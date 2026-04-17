"""
Thresholds calibrated at coord_scale=1000; scale at runtime with ``scale / 1000``.

Rationale (all norm-space at REF 1000 unless noted):
- Lengths / areas scale with ``coord_scale`` (see design §4.4).
- Values are **engineering defaults**: stable QA-ish behaviour, not tuned on a
  specific dataset; change only after measuring on real data.

See ``metadata/plans/2026-04-15_1658_metadata_next/design.md`` §4.2–§4.4.
"""

from __future__ import annotations

REF_COORD_SCALE = 1000

# --- distances / deltas (same units as norm UV at REF scale) ---
# Ignore an axis for single-axis output when |delta| is tiny (noise / tie on that axis).
MIN_ABS_DELTA_U_REF = 100
MIN_ABS_DELTA_V_REF = 100
# Two representative points closer than this (after IoU check) → relation unreliable.
NEAR_CENTER_DIST_REF = 100

# --- area (square of norm units at REF scale) ---
# Default is permissive to keep enrichment predictable across unit tests and
# synthetic fixtures; downstream QA/export stages can apply stricter filtering
# if needed.
MIN_AREA_ABS_REF = 1

# --- IoU ---
# If IoU > this value, drop the ordered pair. **0.3 is very strict** (mild overlap
# already discarded); tune on real data (design §4.2).
AMBIGUOUS_IOU = 0.5

# --- containment (IoA w.r.t. smaller box) ---
# IoU can be small even when one box almost fully contains the other (large vs small).
# Drop such pairs when intersection covers most of the smaller box.
CONTAINMENT_IOA = 0.8

# --- max aspect ratio for bbox (filters use max(w/h, h/w), w,h = box sides) ---
# Values >> 1 mean **very elongated** boxes (thin strip or flat bar in norm space).
# **12** is an arbitrary engineering cap: drop only *pathological* slivers (bad det /
# line-like artefacts), not a statistically tuned constant. Typical real objects are
# often < ~8–10 on this metric; raise if your domain has legitimate long buses/poles
# in 2D bbox form; lower if you see many false positives from needle boxes.
MAX_ASPECT_RATIO = 12.0


def scale_length(value_at_ref: float, coord_scale: int) -> float:
    return value_at_ref * (coord_scale / REF_COORD_SCALE)


def scale_area(value_at_ref: float, coord_scale: int) -> float:
    f = coord_scale / REF_COORD_SCALE
    return value_at_ref * (f * f)
