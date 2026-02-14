from __future__ import annotations

from shottrainer.replay.timeline import index_of_nearest, slice_window
from shottrainer.tracking.models import TrackingSample


def _samples(n: int, dt: float = 0.05) -> list[TrackingSample]:
    return [
        TrackingSample(timestamp=i * dt, x_px=0.0, y_px=0.0, x_mm=float(i), y_mm=float(-i))
        for i in range(n)
    ]


def test_slice_window_returns_inclusive_range():
    s = _samples(60)
    out = slice_window(s, centre_ts=1.0, pre_ms=200, post_ms=200)
    timestamps = [x.timestamp for x in out]
    assert timestamps[0] >= 0.8 - 1e-9
    assert timestamps[-1] <= 1.2 + 1e-9
    assert all(0.8 <= t <= 1.2 for t in timestamps)


def test_slice_window_handles_empty():
    assert slice_window([], 0.0, 100, 100) == []


def test_index_of_nearest_picks_closest():
    s = _samples(20)
    idx = index_of_nearest(s, 0.46)
    assert idx is not None
    assert s[idx].timestamp == 0.45 or s[idx].timestamp == 0.5


def test_index_of_nearest_handles_extremes():
    s = _samples(5)
    assert index_of_nearest(s, -10.0) == 0
    assert index_of_nearest(s, 100.0) == 4


def test_index_of_nearest_empty():
    assert index_of_nearest([], 0.0) is None
