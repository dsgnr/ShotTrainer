from __future__ import annotations

import csv
from pathlib import Path

import pytest

from shottrainer.services.exporter import export_session_csv
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.models import TrackingSample


@pytest.fixture()
def repo() -> SessionRepository:
    engine = make_engine(":memory:")
    init_database(engine)
    return SessionRepository(engine)


def test_exports_two_csv_files(tmp_path: Path, repo: SessionRepository):
    sid = repo.create_session(name="t")
    repo.append_trace(
        sid,
        [
            TrackingSample(timestamp=0.0, x_px=10.0, y_px=20.0, x_mm=1.0, y_mm=-1.0),
            TrackingSample(timestamp=0.1, x_px=12.0, y_px=22.0, x_mm=1.2, y_mm=-1.2),
        ],
    )
    repo.add_shot(sid, ts=0.05, x_mm=0.5, y_mm=-0.5, audio_level=0.4, confidence=0.9)

    out = export_session_csv(repo, sid, tmp_path)
    assert len(out) == 2
    shots_path, trace_path = out
    assert shots_path.exists()
    assert trace_path.exists()

    with shots_path.open() as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["index", "timestamp", "x_mm", "y_mm", "audio_level", "confidence", "score"]
    assert len(rows) == 2

    with trace_path.open() as f:
        rows = list(csv.reader(f))
    assert rows[0][0] == "timestamp"
    assert len(rows) == 3


def test_exports_handles_no_shots(tmp_path: Path, repo: SessionRepository):
    sid = repo.create_session()
    out = export_session_csv(repo, sid, tmp_path)
    assert all(p.exists() for p in out)
    with out[0].open() as f:
        assert sum(1 for _ in f) == 1  # header only
