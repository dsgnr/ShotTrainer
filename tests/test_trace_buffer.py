from __future__ import annotations

from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.tracking.models import TrackingSample


def _s(ts: float) -> TrackingSample:
    return TrackingSample(timestamp=ts, x_px=0.0, y_px=0.0)


def test_capacity_drops_oldest():
    buf = TraceBuffer(capacity=3)
    for t in (0.0, 0.1, 0.2, 0.3):
        buf.append(_s(t))
    snap = buf.snapshot()
    assert [s.timestamp for s in snap] == [0.1, 0.2, 0.3]


def test_nearest_picks_closer_neighbour():
    buf = TraceBuffer()
    for t in (1.0, 1.1, 1.2, 1.3):
        buf.append(_s(t))
    n = buf.nearest(1.16)
    assert n is not None
    assert n.timestamp == 1.2


def test_nearest_returns_none_when_empty():
    assert TraceBuffer().nearest(0.0) is None


def test_window_inclusive_bounds():
    buf = TraceBuffer()
    for t in (0.0, 0.1, 0.2, 0.3, 0.4):
        buf.append(_s(t))
    w = buf.window(0.1, 0.3)
    assert [s.timestamp for s in w] == [0.1, 0.2, 0.3]


def test_clear_empties_buffer():
    buf = TraceBuffer()
    buf.append(_s(1.0))
    buf.clear()
    assert len(buf) == 0
