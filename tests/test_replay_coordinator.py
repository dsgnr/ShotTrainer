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
    window = coord.shot_window(sid, shots[0], pre_ms=500, post_ms=500)
    assert window.split_index is not None
    centre_sample = window.samples[window.split_index]
    assert abs(centre_sample.timestamp - 1.0) < 0.05
