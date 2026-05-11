from __future__ import annotations

import pytest

from shottrainer.services.replay_coordinator import ReplayCoordinator
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.models import TrackingSample


@pytest.fixture()
def repo() -> SessionRepository:
    engine = make_engine(":memory:")
    init_database(engine)
    return SessionRepository(engine)


def _samples(n: int, dt: float = 0.05) -> list[TrackingSample]:
    return [
        TrackingSample(timestamp=i * dt, x_px=0.0, y_px=0.0, x_mm=float(i), y_mm=-float(i))
        for i in range(n)
    ]


def test_shot_window_finds_split(repo: SessionRepository):
    sid = repo.create_session()
    repo.append_trace(sid, _samples(60, dt=0.05))  # 0.0..2.95
    repo.add_shot(sid, ts=1.0, x_mm=0.0, y_mm=0.0, audio_level=0.4, confidence=0.9)
    coord = ReplayCoordinator(repo)
    shots = repo.list_shots(sid)
    window = coord.shot_window(sid, shots[0].ts, pre_ms=500, post_ms=500)
    assert window.split_index is not None
    centre_sample = window.samples[window.split_index]
    assert abs(centre_sample.timestamp - 1.0) < 0.05


def test_release_index_respects_custom_release_ms(repo: SessionRepository):
    """A longer ``release_ms`` should mark the release window earlier
    in the trace so more samples land in the release phase."""
    sid = repo.create_session()
    repo.append_trace(sid, _samples(60, dt=0.05))  # 0.0 to 2.95
    repo.add_shot(sid, ts=1.5, x_mm=0.0, y_mm=0.0, audio_level=0.4, confidence=0.9)
    coord = ReplayCoordinator(repo)
    shots = repo.list_shots(sid)

    short = coord.shot_window(sid, shots[0].ts, pre_ms=1000, post_ms=200, release_ms=200)
    long_ = coord.shot_window(sid, shots[0].ts, pre_ms=1000, post_ms=200, release_ms=600)
    assert short.release_index is not None
    assert long_.release_index is not None
    # A longer release window starts earlier in the same sample list,
    # so its release_index should be the smaller of the two.
    assert long_.release_index < short.release_index


def test_release_index_default_is_250ms(repo: SessionRepository):
    """Calling ``shot_window`` without ``release_ms`` keeps the
    historical 250 ms behaviour."""
    sid = repo.create_session()
    repo.append_trace(sid, _samples(60, dt=0.05))
    repo.add_shot(sid, ts=1.5, x_mm=0.0, y_mm=0.0, audio_level=0.4, confidence=0.9)
    coord = ReplayCoordinator(repo)
    shots = repo.list_shots(sid)

    default = coord.shot_window(sid, shots[0].ts, pre_ms=1000, post_ms=200)
    explicit = coord.shot_window(sid, shots[0].ts, pre_ms=1000, post_ms=200, release_ms=250)
    assert default.release_index == explicit.release_index
