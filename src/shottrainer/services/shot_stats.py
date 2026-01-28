"""Numbers about shots and traces.

Pure functions over shot positions. The widget layer formats the numbers,
the recorder writes them to the database, this module computes them.
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
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            d = math.hypot(positions[i][0] - positions[j][0], positions[i][1] - positions[j][1])
            if d > spread:
                spread = d

    return ShotStats(
        count=len(positions),
        mean_x_mm=cx,
        mean_y_mm=cy,
        extreme_spread_mm=spread,
        mean_radius_mm=mean_r,
    )
