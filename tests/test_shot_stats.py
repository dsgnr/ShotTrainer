from __future__ import annotations

import math

from shottrainer.services.shot_stats import compute_stats


def test_empty_returns_zeros():
    s = compute_stats([])
    assert s.count == 0
    assert s.extreme_spread_mm == 0.0


def test_single_shot_has_zero_spread_and_radius():
    s = compute_stats([(2.0, -3.0)])
    assert s.count == 1
    assert s.mean_x_mm == 2.0
    assert s.mean_y_mm == -3.0
    assert s.extreme_spread_mm == 0.0
    assert s.mean_radius_mm == 0.0


def test_extreme_spread_picks_max_pairwise():
    points = [(0.0, 0.0), (3.0, 4.0), (-2.0, -1.0)]
    s = compute_stats(points)
    assert math.isclose(s.extreme_spread_mm, 5 + 0.0, rel_tol=0, abs_tol=0.5) or s.extreme_spread_mm > 5
    # the max distance between (0,0) and (3,4) is 5; (3,4) to (-2,-1) is sqrt(50)~7.07
    assert math.isclose(s.extreme_spread_mm, math.hypot(5, 5), abs_tol=1e-6)


def test_mean_radius_is_average_distance_from_centre():
    points = [(0.0, 0.0), (10.0, 0.0)]
    s = compute_stats(points)
    assert s.mean_x_mm == 5.0
    assert s.mean_y_mm == 0.0
    assert math.isclose(s.mean_radius_mm, 5.0)
