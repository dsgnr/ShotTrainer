"""Numbers about shots and traces.

Plain functions over shot positions and trace points. The widget
layer formats the results, the recorder writes them, this module
just computes them.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShotStats:
    count: int
    mean_x_mm: float
    mean_y_mm: float
    extreme_spread_mm: float        # largest centre-to-centre distance
    mean_radius_mm: float           # average distance from the group centre


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
    if not positions:
        return ShotStats(0, 0.0, 0.0, 0.0, 0.0)

    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)

    radii = [math.hypot(x - cx, y - cy) for x, y in positions]
    mean_r = sum(radii) / len(radii)

    spread = 0.0
    for i, (xi, yi) in enumerate(positions):
        for xj, yj in positions[i + 1 :]:
            d = math.hypot(xi - xj, yi - yj)
            spread = max(spread, d)

    return ShotStats(
        count=len(positions),
        mean_x_mm=cx,
        mean_y_mm=cy,
        extreme_spread_mm=spread,
        mean_radius_mm=mean_r,
    )


def compute_trace_stats(points: Sequence[tuple[float, float]]) -> TraceStats:
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
