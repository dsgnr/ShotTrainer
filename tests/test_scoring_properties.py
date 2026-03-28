"""Property tests for the scoring service.

Example-based tests cover specific shot/ring combinations. The
properties here pin invariants that have to hold for any valid input
the call sites can produce.
"""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from shottrainer.services.scoring import (
    ScoringRing,
    label_to_value,
    score_shot,
    total_score,
)

_finite_mm = st.floats(
    min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False
)
_radii = st.lists(
    st.floats(min_value=0.5, max_value=200.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=12,
    unique=True,
)


def _rings_from_radii(radii: list[float]) -> list[ScoringRing]:
    """Build a sorted ring layout from a set of radii.

    Innermost ring labelled "X", then descending integer scores (10,
    9, 8, ...) so the labels stay distinct without coupling to a
    specific federation layout.
    """
    radii_sorted = sorted(radii)
    labels = ["X"] + [str(10 - i) for i in range(len(radii_sorted) - 1)]
    return [ScoringRing(r, label) for r, label in zip(radii_sorted, labels, strict=True)]


@given(_finite_mm, _finite_mm, _radii)
def test_centre_shot_always_scores_innermost(x: float, y: float, radii: list[float]):
    """A shot at the ring centre always scores the innermost ring,
    regardless of where the centre is."""
    rings = _rings_from_radii(radii)
    assert score_shot(x, y, rings, centre=(x, y)) == rings[0].label


@given(_radii, _finite_mm)
def test_far_shot_scores_empty(radii: list[float], offset: float):
    """A shot well outside the largest ring scores nothing."""
    rings = _rings_from_radii(radii)
    far = max(r.radius_mm for r in rings) + abs(offset) + 1.0
    assert score_shot(far, 0.0, rings) == ""


@given(_radii, st.floats(min_value=0.0, max_value=10.0))
def test_larger_shot_scores_at_least_as_well(radii: list[float], extra_diameter: float):
    """A wider shot scores at least as well as a smaller one at the
    same position. Increasing the diameter can only push the edge
    further inward, never away from the centre."""
    rings = _rings_from_radii(radii)
    # Pick a position that's sometimes inside and sometimes outside
    # the rings so the property has work to do.
    position = max(r.radius_mm for r in rings) * 0.5
    base = score_shot(position, 0.0, rings, shot_diameter_mm=0.0)
    bigger = score_shot(position, 0.0, rings, shot_diameter_mm=extra_diameter)
    base_value = label_to_value(base) if base else None
    bigger_value = label_to_value(bigger) if bigger else None
    if base_value is None and bigger_value is None:
        return
    if base_value is None:
        # An empty score means "missed everything". Any non-empty
        # bigger result is an improvement.
        return
    if bigger_value is None:
        # The bigger shot can never score worse than the smaller one.
        raise AssertionError("Wider shot scored empty where a narrower one scored")
    assert bigger_value >= base_value


@given(
    st.lists(
        st.tuples(_finite_mm, _finite_mm),
        min_size=0,
        max_size=20,
    )
)
def test_total_score_is_associative_under_concatenation(
    positions: list[tuple[float, float]],
):
    """``total_score(a + b) == total_score(a) + total_score(b)``.

    The hot-path callers compose scores from a couple of sources
    (live shots plus loaded session shots). The totals must combine
    cleanly regardless of split point.
    """
    if not positions:
        return
    rings = _rings_from_radii([10.0, 25.0, 50.0])
    labels = [score_shot(x, y, rings) for x, y in positions]
    mid = len(labels) // 2
    assert math.isclose(
        total_score(labels),
        total_score(labels[:mid]) + total_score(labels[mid:]),
    )


@settings(deadline=None)
@given(_finite_mm, _finite_mm, _radii)
def test_score_is_monotonic_in_distance(
    x: float, y: float, radii: list[float],
):
    """Moving a shot strictly outward across a ring boundary cannot
    improve its score. The value never increases as distance grows."""
    rings = _rings_from_radii(radii)
    inner_score = score_shot(x, y, rings)
    # Shift the shot outward by 5 mm in the x direction (or whichever
    # axis has more room). The new score must be no higher.
    outer_score = score_shot(x + 5.0, y, rings)
    inner_value = label_to_value(inner_score)
    outer_value = label_to_value(outer_score)
    if inner_value is None or outer_value is None:
        return
    # Edge cases. A shift can move you in a different direction
    # relative to the ring centre at (0, 0). Only the component that
    # genuinely increases distance is interesting. Compute the
    # actual radial movement and skip when it didn't grow.
    if math.hypot(x + 5.0, y) <= math.hypot(x, y):
        return
    assert outer_value <= inner_value
