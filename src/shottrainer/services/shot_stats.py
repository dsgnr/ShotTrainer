"""Numbers about shots and traces.

Plain functions over shot positions and trace points. The widget
layer formats the results, the recorder writes them, this module
just computes them.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class ShotStats:
    count: int
    mean_x_mm: float
    mean_y_mm: float
    extreme_spread_mm: float  # largest centre-to-centre distance
    mean_radius_mm: float  # average distance from the group centre


@dataclass(frozen=True, slots=True)
class TraceStats:
    """Stability numbers from a stretch of trace, usually the pre-shot window.

    ``hold_tremor_mm`` is the RMS deviation of the trace from its
    average position. Smaller is steadier. ``trace_length_mm`` is
    the total distance the aim point covered across the window,
    which is a rough proxy for how unsettled the hold was.
    """

    samples: int
    hold_tremor_mm: float
    trace_length_mm: float
    mean_x_mm: float
    mean_y_mm: float


def compute_stats(positions: Sequence[tuple[float, float]]) -> ShotStats:
    """Group statistics for a list of shot positions in mm.

    ``extreme_spread_mm`` is the largest centre-to-centre
    distance between any two shots. The pairwise distance grid
    runs in numpy so a session that ends up with hundreds of
    shots doesn't slow the repaint loop down with a Python loop.
    """
    if not positions:
        return ShotStats(0, 0.0, 0.0, 0.0, 0.0)

    points = np.asarray(positions, dtype=np.float64)
    cx, cy = points.mean(axis=0)

    radii = np.hypot(points[:, 0] - cx, points[:, 1] - cy)
    mean_r = float(radii.mean())

    if len(points) >= 2:
        # Pairwise distances via broadcasting. The spread is the
        # max over the full square. The matrix is symmetric and
        # the diagonal is zero, so ``np.max`` over the whole
        # thing gives the right answer.
        deltas = points[:, None, :] - points[None, :, :]
        spread = float(np.max(np.hypot(deltas[..., 0], deltas[..., 1])))
    else:
        spread = 0.0

    return ShotStats(
        count=len(points),
        mean_x_mm=float(cx),
        mean_y_mm=float(cy),
        extreme_spread_mm=spread,
        mean_radius_mm=mean_r,
    )


def compute_trace_stats(points: Sequence[tuple[float, float]]) -> TraceStats:
    """Tremor and total-travel numbers across one trace window.

    ``hold_tremor_mm`` is the RMS distance of the trace from its
    average position. Smaller means a steadier hold.
    ``trace_length_mm`` is the cumulative path the aim point
    covered, a rough proxy for how busy the hold was.
    """
    if not points:
        return TraceStats(0, 0.0, 0.0, 0.0, 0.0)

    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n

    sq = 0.0
    length = 0.0
    prev: tuple[float, float] | None = None
    for x, y in points:
        sq += (x - cx) ** 2 + (y - cy) ** 2
        if prev is not None:
            length += math.hypot(x - prev[0], y - prev[1])
        prev = (x, y)
    tremor = math.sqrt(sq / n)
    return TraceStats(
        samples=n,
        hold_tremor_mm=tremor,
        trace_length_mm=length,
        mean_x_mm=cx,
        mean_y_mm=cy,
    )


def time_inside_radius(
    points: Sequence[tuple[float, float]],
    radius_mm: float,
    centre: tuple[float, float] = (0.0, 0.0),
) -> float:
    """Fraction of trace samples that fall within ``radius_mm`` of ``centre``.

    Returns ``0.0`` when the trace is empty.
    """
    if not points:
        return 0.0
    cx, cy = centre
    inside = sum(1 for x, y in points if math.hypot(x - cx, y - cy) <= radius_mm)
    return inside / len(points)
