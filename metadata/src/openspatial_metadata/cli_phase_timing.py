"""
Thread-safe per-phase wall-clock timings for CLI runs (openspatial-metadata).

Used when ``--timing`` is passed: aggregates seconds per phase name across
records and worker threads, then prints a short summary to stderr.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional


class PhaseTimer:
    """Accumulate ``perf_counter`` deltas per phase (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.totals: Dict[str, float] = {}
        self.counts: Dict[str, int] = {}

    def add(self, phase: str, seconds: float) -> None:
        dt = max(0.0, float(seconds))
        with self._lock:
            self.totals[phase] = self.totals.get(phase, 0.0) + dt
            self.counts[phase] = self.counts.get(phase, 0) + 1

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        with self._lock:
            out: Dict[str, Dict[str, float]] = {}
            for phase, total in self.totals.items():
                c = int(self.counts.get(phase, 0))
                out[phase] = {
                    "total_s": float(total),
                    "count": float(c),
                    "mean_ms": float((total / c) * 1000.0) if c else 0.0,
                }
            return out


@contextmanager
def timed_phase(timer: Optional[PhaseTimer], phase: str) -> Iterator[None]:
    if timer is None:
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        timer.add(phase, time.perf_counter() - t0)


def format_timing_lines(
    *,
    label: str,
    wall_s: float,
    phase_timer: Optional[PhaseTimer],
    n_records: Optional[int] = None,
) -> List[str]:
    lines = [
        f"[openspatial-metadata][timing] {label} wall_clock_s={wall_s:.3f}"
        + (f" records={int(n_records)}" if n_records is not None else "")
        + " (phase total_s sums worker threads; can exceed wall_clock under parallelism)"
    ]
    if phase_timer is None:
        return lines
    snap = phase_timer.snapshot()
    if not snap:
        lines.append("[openspatial-metadata][timing]   (no phase samples)")
        return lines
    for phase in sorted(snap.keys()):
        row = snap[phase]
        total = row["total_s"]
        cnt = int(row["count"])
        mean = row["mean_ms"]
        pct = (100.0 * total / wall_s) if wall_s > 0 else 0.0
        lines.append(
            f"[openspatial-metadata][timing]   {phase}: total_s={total:.3f} "
            f"n={cnt} mean_ms={mean:.2f} (~{pct:.1f}% of split wall; see note above)"
        )
    return lines
