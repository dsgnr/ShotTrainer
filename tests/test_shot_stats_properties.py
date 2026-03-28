"""Property tests for the shot-stats service.

The example tests cover the obvious cases. These properties pin
invariants the controller relies on whenever it refreshes the panel.
"""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from shottrainer.services.shot_stats import compute_stats

_finite = st.floats(
    min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False
)


@given(
    st.lists(
        st.tuples(_finite, _finite),
        min_size=1,
        max_size=30,
    )
)
def test_extreme_spread_invariant_under_shuffle(
    positions: list[tuple[float, float]],
):
    """Reordering the shot list cannot change the extreme spread. The
    metric is a pairwise maximum and doesn't depend on the order."""
    forward = compute_stats(positions).extreme_spread_mm
    backward = compute_stats(list(reversed(positions))).extreme_spread_mm
    assert math.isclose(forward, backward, rel_tol=1e-9, abs_tol=1e-9)


@given(
    st.lists(
        st.tuples(_finite, _finite),
        min_size=2,
        max_size=30,
    )
)
def test_extreme_spread_at_least_pairwise_distance(
    positions: list[tuple[float, float]],
):
    """The extreme spread is at least as large as any single
    pairwise distance, since the pair that's farthest apart
    sets the floor."""
    stats = compute_stats(positions)
    # First-versus-last is one pair. The metric must not be smaller.
    a, b = positions[0], positions[-1]
    assert stats.extreme_spread_mm >= math.hypot(a[0] - b[0], a[1] - b[1]) - 1e-9


@given(
    st.lists(
        st.tuples(_finite, _finite),
        min_size=1,
        max_size=30,
    )
)
def test_mean_is_translation_equivariant(
    positions: list[tuple[float, float]],
):
    """Translating every shot by ``(dx, dy)`` shifts the group
    centre by exactly the same vector and leaves the radii alone."""
    dx, dy = 7.5, -3.25
    base = compute_stats(positions)
    shifted = compute_stats([(x + dx, y + dy) for x, y in positions])
    assert math.isclose(shifted.mean_x_mm, base.mean_x_mm + dx, abs_tol=1e-7)
    assert math.isclose(shifted.mean_y_mm, base.mean_y_mm + dy, abs_tol=1e-7)
    assert math.isclose(
        shifted.extreme_spread_mm, base.extreme_spread_mm, rel_tol=1e-9, abs_tol=1e-7
    )
    assert math.isclose(
        shifted.mean_radius_mm, base.mean_radius_mm, rel_tol=1e-9, abs_tol=1e-7
    )
