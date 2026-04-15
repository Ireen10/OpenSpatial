"""
Thresholds calibrated at coord_scale=1000; scale at runtime with ``scale / 1000``.

Rationale (all norm-space at REF 1000 unless noted):
- Lengths / areas scale with ``coord_scale`` (see design §4.4).
- Values are **engineering defaults**: stable QA-ish behaviour, not tuned on a
  specific dataset; change only after measuring on real data.

See ``metadata/plans/2026-04-16_0300_metadata_next/design.md`` §4.2–§4.4.
"""

from __future__ import annotations

REF_COORD_SCALE = 1000

# --- distances / deltas (same units as norm UV at REF scale) ---
# Ignore an axis for single-axis output when |delta| is tiny (noise / tie on that axis).
MIN_ABS_DELTA_U_REF = 12
MIN_ABS_DELTA_V_REF = 12
# Two representative points closer than this (after IoU check) → relation unreliable.
NEAR_CENTER_DIST_REF = 16

# --- area (square of norm units at REF scale) ---
# ~13×13 at scale 1000: drop speck boxes before relations.
MIN_AREA_ABS_REF = 180

# --- IoU ---
# Above this, two bboxes overlap so much that left/right/above/below from centers
# is often misleading → drop the ordered pair (design §4.2).
AMBIGUOUS_IOU = 0.82

# --- "tie band": magnitude ratio only, NOT part of compass / bearing math ---
# When BOTH |du| and |dv| are already >= their min_abs thresholds, we *could* emit
# a composite relation. Design (§4.2) adds a conservative rule: if the two
# magnitudes are almost equal, the displacement is nearly along a diagonal in
# uv-space, so picking a single "main" predicate is weak and composite QA can
# feel arbitrary → **drop the whole pair**.
#
#   ratio = min(|du|, |dv|) / max(|du|, |dv|)   # always in [0, 1]
#   if ratio >= TIE_BAND_MIN_OVER_MAX_REF: discard (do not emit composite).
#
# This ratio never decides sign(left/right/above/below); signs come only from du, dv.
TIE_BAND_MIN_OVER_MAX_REF = 0.88

# --- aspect ratio max (w/h or h/w) for boxes ---
MAX_ASPECT_RATIO = 24.0


def scale_length(value_at_ref: float, coord_scale: int) -> float:
    return value_at_ref * (coord_scale / REF_COORD_SCALE)


def scale_area(value_at_ref: float, coord_scale: int) -> float:
    f = coord_scale / REF_COORD_SCALE
    return value_at_ref * (f * f)
