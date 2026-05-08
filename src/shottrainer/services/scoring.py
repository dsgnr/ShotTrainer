"""Work out what a shot scores.

Plain functions over a position, a shot diameter, and a ring
layout. The recorder uses this to score shots as they're captured
and write the result to the database, so the scoring logic
deliberately doesn't depend on any of the widgets.

The convention here is "edge of the shot touches the ring". The
shot scores the innermost ring whose circle the shot's outer edge
intersects (or sits inside), rather than where its centre lies.
That's how paper-target federations do it.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScoringRing:
    """A scoring ring with a radius in mm and a label.

    No UI types involved, so this module sits at the services
    layer without dragging widget code in.
    """

    radius_mm: float
    label: str


def score_shot(
    x_mm: float,
    y_mm: float,
    rings: Sequence[ScoringRing],
    *,
    shot_diameter_mm: float = 0.0,
    centre: tuple[float, float] = (0.0, 0.0),
) -> str:
    """Return the label of the smallest ring this shot scores in.

    ``rings`` has to come in sorted by radius, smallest first. We
    walk them in order and return the label of the first ring the
    shot's circle overlaps. Sorting once when the face is loaded
    is cheaper than sorting on every shot.

    Returns an empty string if the shot misses every ring or no
    rings were supplied.

    The shot is treated as a circle of ``shot_diameter_mm``. With
    ``shot_diameter_mm == 0`` we fall back to "is the centre
    inside the ring", which is useful for tests and for trace
    points (which have no diameter).
    """
    if not rings:
        return ""

    cx, cy = centre
    distance = math.hypot(x_mm - cx, y_mm - cy)
    margin = shot_diameter_mm / 2.0

    for ring in rings:
        if distance - margin <= ring.radius_mm:
            return ring.label
    return ""


def label_to_value(label: str) -> float | None:
    """Best-effort numeric value for a ring label.

    Federation rings are usually labelled with their value
    (``1`` to ``10``) plus a centre ``X`` that scores the same as
    a ``10``. Anything else returns ``None``.
    """
    if not label:
        return None
    if label.upper() == "X":
        return 10.0
    try:
        return float(label)
    except ValueError:
        return None


def total_score(scores: Iterable[str]) -> float:
    """Add up the numeric values for a list of ring labels.

    Labels that don't parse as numbers (or ``X``) count as zero
    rather than blowing up the total. That way a session that
    mixes disciplines (or has a few unscorable shots) still
    produces a number the panels can show.
    """
    total = 0.0
    for s in scores:
        v = label_to_value(s)
        if v is not None:
            total += v
    return total
