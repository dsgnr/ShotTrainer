from __future__ import annotations

import pytest

from shottrainer.services.session_recorder import RecorderConfig, SessionRecorder
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.models import TrackingSample


@pytest.fixture()
def recorder() -> SessionRecorder:
    engine = make_engine(":memory:")
    init_database(engine)
    repo = SessionRepository(engine)
    return SessionRecorder(repo, RecorderConfig(flush_every=10, flush_seconds=10.0))


def _sample(ts: float) -> TrackingSample:
    return TrackingSample(timestamp=ts, x_px=ts * 10, y_px=-ts * 10, x_mm=ts, y_mm=-ts)


def test_cannot_double_start(recorder: SessionRecorder):
    recorder.start(name="a")
    with pytest.raises(RuntimeError):
        recorder.start(name="b")


def test_samples_are_flushed_in_batches(recorder: SessionRecorder):
    sid = recorder.start()
    for t in range(9):
        recorder.add_sample(_sample(t * 0.1))
    # Below the flush threshold. Still pending.
    assert recorder._repo.trace_count(sid) == 0
    # 10th sample triggers a flush.
    recorder.add_sample(_sample(1.0))
    assert recorder._repo.trace_count(sid) == 10


def test_stop_flushes_remaining(recorder: SessionRecorder):
    sid = recorder.start()
    for t in range(3):
        recorder.add_sample(_sample(t * 0.1))
    recorder.stop()
    repo = recorder._repo
    assert repo.trace_count(sid) == 3
    summaries = repo.list_sessions()
    assert summaries[0].ended_at is not None


def test_add_shot_returns_id_and_persists(recorder: SessionRecorder):
    sid = recorder.start()
    recorder.add_sample(_sample(0.0))
    shot_id = recorder.add_shot(ts=0.5, x_mm=1.0, y_mm=-1.0, audio_level=0.4, confidence=0.8)
    assert shot_id is not None
    repo = recorder._repo
    shots = repo.list_shots(sid)
    assert len(shots) == 1
    assert shots[0].x_mm == 1.0


def test_no_shot_outside_session(recorder: SessionRecorder):
    assert recorder.add_shot(ts=0.0, x_mm=0.0, y_mm=0.0, audio_level=0.0, confidence=0.0) is None
