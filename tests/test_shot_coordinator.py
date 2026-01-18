from __future__ import annotations

from shottrainer.audio.models import ShotEvent
from shottrainer.services.shot_coordinator import ShotCoordinator, ShotCoordinatorSettings
from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.tracking.models import TrackingSample


def _s(ts: float, x_mm: float = 0.0) -> TrackingSample:
    return TrackingSample(timestamp=ts, x_px=0.0, y_px=0.0, x_mm=x_mm, y_mm=0.0)


def _event(ts: float) -> ShotEvent:
    return ShotEvent(timestamp=ts, audio_level=0.5, sample_rate=44100)


def test_handle_shot_picks_nearest_sample():
    buf = TraceBuffer()
    buf.extend([_s(0.0, 0.0), _s(0.5, 5.0), _s(1.0, 10.0)])
    coord = ShotCoordinator(buf)
    result = coord.handle_shot(_event(0.6))
    assert result.sample is not None
    assert result.sample.timestamp == 0.5
    assert result.sample.x_mm == 5.0


def test_handle_shot_returns_window():
    buf = TraceBuffer()
    for t in range(0, 30):
        buf.append(_s(t * 0.1))
    coord = ShotCoordinator(buf, ShotCoordinatorSettings(pre_shot_ms=500, post_shot_ms=500))
    result = coord.handle_shot(_event(1.0))
    timestamps = [s.timestamp for s in result.trace]
    assert all(0.5 <= t <= 1.5 for t in timestamps)
    assert len(result.trace) >= 5


def test_handle_shot_with_empty_buffer():
    buf = TraceBuffer()
    coord = ShotCoordinator(buf)
    result = coord.handle_shot(_event(1.0))
    assert result.sample is None
    assert result.trace == []
