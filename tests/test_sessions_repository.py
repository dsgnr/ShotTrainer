from __future__ import annotations

import pytest

from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.models import TrackingSample


@pytest.fixture()
def repo() -> SessionRepository:
    engine = make_engine(":memory:")
    init_database(engine)
    return SessionRepository(engine)


def _sample(ts: float, x: float = 0.0, y: float = 0.0) -> TrackingSample:
    return TrackingSample(
        timestamp=ts, x_px=x, y_px=y, x_mm=x, y_mm=y, confidence=1.0, frame_id=int(ts * 100)
    )


def test_create_and_list_sessions(repo: SessionRepository):
    sid = repo.create_session(name="evening practice")
    summaries = repo.list_sessions()
    assert len(summaries) == 1
    assert summaries[0].id == sid
    assert summaries[0].name == "evening practice"
    assert summaries[0].shot_count == 0


def test_append_trace_is_batched_and_queryable(repo: SessionRepository):
    sid = repo.create_session()
    samples = [_sample(t / 10.0, x=t, y=-t) for t in range(50)]
    inserted = repo.append_trace(sid, samples)
    assert inserted == 50
    assert repo.trace_count(sid) == 50

    loaded = repo.load_trace(sid)
    assert len(loaded) == 50
    assert loaded[0].timestamp == pytest.approx(0.0)
    assert loaded[-1].x_px == 49.0


def test_trace_window_query(repo: SessionRepository):
    sid = repo.create_session()
    repo.append_trace(sid, [_sample(t / 10.0) for t in range(100)])
    window = repo.load_trace(sid, start_ts=2.0, end_ts=3.0)
    assert all(2.0 <= s.timestamp <= 3.0 for s in window)
    assert len(window) == 11


def test_add_and_list_shots(repo: SessionRepository):
    sid = repo.create_session()
    repo.add_shot(sid, ts=1.5, x_mm=2.0, y_mm=-1.0, audio_level=0.4, confidence=0.9, score="9")
    repo.add_shot(sid, ts=3.2, x_mm=0.5, y_mm=0.1, audio_level=0.5, confidence=0.85)
    shots = repo.list_shots(sid)
    assert len(shots) == 2
    assert shots[0].ts == 1.5
    assert shots[1].x_mm == 0.5

    summary = repo.list_sessions()[0]
    assert summary.shot_count == 2


def test_session_summary_includes_total_score(repo: SessionRepository):
    sid = repo.create_session(name="qual")
    repo.add_shot(sid, ts=0.1, x_mm=0.0, y_mm=0.0, audio_level=0.4, confidence=0.9, score="10")
    repo.add_shot(sid, ts=0.2, x_mm=0.0, y_mm=0.0, audio_level=0.4, confidence=0.9, score="X")
    repo.add_shot(sid, ts=0.3, x_mm=0.0, y_mm=0.0, audio_level=0.4, confidence=0.9, score="9")
    summary = repo.list_sessions()[0]
    assert summary.shot_count == 3
    # 10 + 10 (X) + 9 = 29
    assert summary.total_score == pytest.approx(29.0)


def test_session_summary_zero_for_unscored_shots(repo: SessionRepository):
    sid = repo.create_session()
    repo.add_shot(sid, ts=0.1, x_mm=0.0, y_mm=0.0, audio_level=0.4, confidence=0.9)
    summary = repo.list_sessions()[0]
    assert summary.total_score == 0.0


def test_delete_session_cascades(repo: SessionRepository):
    sid = repo.create_session()
    repo.append_trace(sid, [_sample(0.0), _sample(0.1)])
    repo.add_shot(sid, ts=0.05, x_mm=0.0, y_mm=0.0, audio_level=0.3, confidence=0.5)
    repo.delete_session(sid)
    assert repo.list_sessions() == []
    assert repo.trace_count(sid) == 0


def test_end_session_records_timestamp(repo: SessionRepository):
    sid = repo.create_session()
    repo.end_session(sid)
    summary = repo.list_sessions()[0]
    assert summary.ended_at is not None


def test_list_sessions_query_count_does_not_grow_with_session_count(repo: SessionRepository):
    """``list_sessions`` must not issue one query per session.

    Pins the query count to a small constant so regressions land here
    rather than in user-visible load times once a shooter has months of
    sessions on disk. With 20 sessions and 60 total shots the expected
    plan is one SELECT for the sessions plus one SELECT for the shots
    of those sessions.
    """
    for i in range(20):
        sid = repo.create_session(name=f"session {i}")
        for _ in range(3):
            repo.add_shot(
                sid, ts=0.1, x_mm=0.0, y_mm=0.0, audio_level=0.5, confidence=0.9, score="9"
            )

    queries: list[str] = []

    from sqlalchemy import event

    def _record(_conn, _cursor, statement, *_args, **_kwargs):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(repo._engine, "before_cursor_execute", _record)
    try:
        summaries = repo.list_sessions()
    finally:
        event.remove(repo._engine, "before_cursor_execute", _record)

    assert len(summaries) == 20
    # One SELECT for sessions, one SELECT for the shots in those sessions.
    assert len(queries) == 2, "list_sessions issued more SELECTs than expected:\n" + "\n".join(
        queries
    )
    assert all(s.shot_count == 3 for s in summaries)
    assert all(s.total_score == pytest.approx(27.0) for s in summaries)
