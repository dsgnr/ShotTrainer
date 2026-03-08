from __future__ import annotations

import math

import pytest

from shottrainer.services.shot_stats import (
    compute_stats,
    compute_trace_stats,
    time_inside_radius,
)


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
    # max pairwise distance is between (3, 4) and (-2, -1), which is sqrt(50).
    assert math.isclose(s.extreme_spread_mm, math.hypot(5, 5), abs_tol=1e-6)


def test_mean_radius_is_average_distance_from_centre():
    points = [(0.0, 0.0), (10.0, 0.0)]
    s = compute_stats(points)
    assert s.mean_x_mm == 5.0
    assert s.mean_y_mm == 0.0
    assert math.isclose(s.mean_radius_mm, 5.0)


def test_trace_stats_empty():
    s = compute_trace_stats([])
    assert s.samples == 0
    assert s.hold_tremor_mm == 0.0
    assert s.trace_length_mm == 0.0


def test_trace_stats_zero_tremor_when_static():
    s = compute_trace_stats([(2.0, 3.0)] * 5)
    assert s.samples == 5
    assert s.hold_tremor_mm == 0.0
    assert s.trace_length_mm == 0.0


def test_trace_length_is_cumulative_distance():
    s = compute_trace_stats([(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)])
    # 3 + 4 = 7
    assert math.isclose(s.trace_length_mm, 7.0)


def test_hold_tremor_matches_rms_distance():
    points = [(-1.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.0, -1.0)]
    s = compute_trace_stats(points)
    # All four points at distance 1 from origin, mean is origin, RMS is 1.
    assert math.isclose(s.hold_tremor_mm, 1.0)
    assert math.isclose(s.mean_x_mm, 0.0, abs_tol=1e-9)
    assert math.isclose(s.mean_y_mm, 0.0, abs_tol=1e-9)


def test_time_inside_radius_counts_samples():
    points = [(0.0, 0.0), (1.0, 0.0), (5.0, 0.0), (-2.0, 0.0)]
    assert time_inside_radius(points, radius_mm=1.5) == pytest.approx(0.5)
    assert time_inside_radius(points, radius_mm=10.0) == 1.0
    assert time_inside_radius([], radius_mm=5.0) == 0.0


def test_time_inside_radius_uses_centre():
    points = [(10.0, 0.0), (12.0, 0.0)]
    assert time_inside_radius(points, radius_mm=1.5, centre=(11.0, 0.0)) == 1.0
