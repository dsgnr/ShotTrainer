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
    scoring_direction: str = "inward",
) -> str:
    """Return the label of the ring this shot scores.

    ``scoring_direction`` controls how the ring list is walked:

    - ``"inward"`` (default): the shot scores the innermost
      (smallest) ring it touches. Standard for ISSF, NSRA, and
      most rifle/pistol disciplines where 10 is in the centre.
    - ``"outward"``: the shot scores the outermost (largest) ring
      it sits inside. Used by some gallery and novelty targets
      where the highest value is at the edge.

    In both cases, "touches" means the shot's outer edge (centre
    distance minus half the shot diameter) is within the ring's
    radius.

    Returns an empty string if the shot misses every ring or no
    rings were supplied.
    """
    if not rings:
        return ""

    cx, cy = centre
    distance = math.hypot(x_mm - cx, y_mm - cy)
    margin = shot_diameter_mm / 2.0
    shot_edge = distance - margin

    if scoring_direction == "outward":
        # Walk from smallest to largest. The first ring the shot
        # is strictly inside wins. Touching the boundary exactly
        # scores the outer ring (shot_edge < radius, not <=),
        # which is the convention for outward-scored targets.
        for ring in sorted(rings, key=lambda r: r.radius_mm):
            if shot_edge < ring.radius_mm:
                return ring.label
        return ""
    else:
        # Walk from smallest to largest (default inward scoring).
        # The first (innermost) ring the shot touches wins.
        for ring in rings:
            if shot_edge <= ring.radius_mm:
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
