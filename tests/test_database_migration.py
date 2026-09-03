"""Schema-migration tests against an on-disk SQLite database."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from shottrainer.sessions.database import init_database, make_engine


def _create_v1_schema(db_path: Path) -> None:
    """Build a minimal v1 sessions database that still has calibration_json.

    Matches what the app would have created before the migration was
    added, so the test runs the real upgrade path rather than a copy.
    """
    engine = make_engine(db_path)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE schema_meta (
                    id INTEGER PRIMARY KEY,
                    version INTEGER NOT NULL,
                    app_version VARCHAR(32) NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(120) NOT NULL DEFAULT '',
                    started_at DATETIME NOT NULL,
                    ended_at DATETIME,
                    notes TEXT NOT NULL DEFAULT '',
                    calibration_json TEXT,
                    target_profile VARCHAR(64) NOT NULL DEFAULT 'default',
                    app_version VARCHAR(32) NOT NULL DEFAULT '',
                    schema_version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
        )
        conn.execute(text("INSERT INTO schema_meta (version, app_version) VALUES (1, '0.0.0')"))
        conn.execute(
            text(
                "INSERT INTO sessions (name, started_at, calibration_json) "
                "VALUES ('legacy', '2025-01-01 00:00:00', '{\"foo\": 1}')"
            )
        )
    engine.dispose()


@pytest.fixture()
def legacy_db(tmp_path: Path) -> Path:
    db = tmp_path / "legacy.db"
    _create_v1_schema(db)
    return db


def test_init_database_drops_calibration_column(legacy_db: Path):
    """Upgrading a v1 database should remove the unused column.

    The session row itself survives so users don't lose history. Only
    the dead column is dropped.
    """
    engine = make_engine(legacy_db)
    init_database(engine)
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)")}
        rows = list(conn.exec_driver_sql("SELECT name FROM sessions").fetchall())
    assert "calibration_json" not in columns
    assert [r[0] for r in rows] == ["legacy"]


def _create_v2_schema(db_path: Path) -> None:
    """Build a v2 sessions database without the category column.

    Used to verify the v2 -> v3 migration adds the column with the
    expected default for existing rows.
    """
    engine = make_engine(db_path)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE schema_meta (
                    id INTEGER PRIMARY KEY,
                    version INTEGER NOT NULL,
                    app_version VARCHAR(32) NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(120) NOT NULL DEFAULT '',
                    started_at DATETIME NOT NULL,
                    ended_at DATETIME,
                    notes TEXT NOT NULL DEFAULT '',
                    target_profile VARCHAR(64) NOT NULL DEFAULT 'default',
                    app_version VARCHAR(32) NOT NULL DEFAULT '',
                    schema_version INTEGER NOT NULL DEFAULT 2
                )
                """
            )
        )
        conn.execute(text("INSERT INTO schema_meta (version, app_version) VALUES (2, '0.0.0')"))
        conn.execute(
            text("INSERT INTO sessions (name, started_at) VALUES ('older', '2025-06-01 00:00:00')")
        )
    engine.dispose()


@pytest.fixture()
def v2_db(tmp_path: Path) -> Path:
    db = tmp_path / "v2.db"
    _create_v2_schema(db)
    return db


def test_init_database_adds_category_column(v2_db: Path):
    """Upgrading a v2 database adds the new ``category`` column.

    Existing rows inherit the ``"practice"`` default so the browser
    can show a category badge straight away.
    """
    engine = make_engine(v2_db)
    init_database(engine)
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)")}
        rows = list(conn.exec_driver_sql("SELECT name, category FROM sessions").fetchall())
    assert "category" in columns
    assert rows == [("older", "practice")]


def _create_populated_v1_schema(db_path: Path) -> None:
    """Build a v1 database with a session, trace samples, and shots.

    The point is to run every migration step against rows that
    actually exist, so any column changes have to deal with real
    data rather than an empty table.
    """
    engine = make_engine(db_path)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE schema_meta (
                    id INTEGER PRIMARY KEY,
                    version INTEGER NOT NULL,
                    app_version VARCHAR(32) NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(120) NOT NULL DEFAULT '',
                    started_at DATETIME NOT NULL,
                    ended_at DATETIME,
                    notes TEXT NOT NULL DEFAULT '',
                    calibration_json TEXT,
                    target_profile VARCHAR(64) NOT NULL DEFAULT 'default',
                    app_version VARCHAR(32) NOT NULL DEFAULT '',
                    schema_version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE trace_samples (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    ts FLOAT NOT NULL,
                    x_px FLOAT NOT NULL,
                    y_px FLOAT NOT NULL,
                    x_mm FLOAT,
                    y_mm FLOAT,
                    confidence FLOAT NOT NULL DEFAULT 1.0,
                    frame_id INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE shots (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    ts FLOAT NOT NULL,
                    x_mm FLOAT,
                    y_mm FLOAT,
                    audio_level FLOAT NOT NULL DEFAULT 0.0,
                    confidence FLOAT NOT NULL DEFAULT 0.0,
                    score VARCHAR(16) NOT NULL DEFAULT ''
                )
                """
            )
        )
        conn.execute(text("INSERT INTO schema_meta (version, app_version) VALUES (1, '0.0.0')"))
        conn.execute(
            text(
                "INSERT INTO sessions (id, name, started_at, target_profile, calibration_json) "
                "VALUES (1, 'evening practice', '2025-02-10 19:00:00', 'nsra-25yd', "
                '\'{"camera": {"focal": 4.0}}\')'
            )
        )
        # A handful of trace samples plus two shots so the migration
        # has to deal with real foreign key rows.
        for i in range(5):
            conn.execute(
                text(
                    "INSERT INTO trace_samples "
                    "(session_id, ts, x_px, y_px, x_mm, y_mm, confidence, frame_id) "
                    "VALUES (1, :ts, :px, :py, :mx, :my, 0.8, :fid)"
                ),
                {
                    "ts": i * 0.05,
                    "px": 100.0 + i,
                    "py": 200.0 + i,
                    "mx": float(i),
                    "my": -float(i),
                    "fid": i,
                },
            )
        conn.execute(
            text(
                "INSERT INTO shots (session_id, ts, x_mm, y_mm, audio_level, confidence, score) "
                "VALUES (1, 0.10, 1.5, -2.0, 0.42, 0.9, '9')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO shots (session_id, ts, x_mm, y_mm, audio_level, confidence, score) "
                "VALUES (1, 0.20, 0.5, 0.5, 0.61, 0.95, '10')"
            )
        )
    engine.dispose()


@pytest.fixture()
def populated_v1_db(tmp_path: Path) -> Path:
    db = tmp_path / "populated_v1.db"
    _create_populated_v1_schema(db)
    return db


def test_full_upgrade_from_v1_keeps_session_trace_and_shot_rows(populated_v1_db: Path):
    """A populated v1 database should upgrade all the way to the current
    schema without losing rows or the links between them."""
    engine = make_engine(populated_v1_db)
    init_database(engine)

    with engine.connect() as conn:
        session_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)")}
        sessions = list(
            conn.exec_driver_sql(
                "SELECT id, name, target_profile, category FROM sessions"
            ).fetchall()
        )
        trace_count = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM trace_samples WHERE session_id = 1"
        ).scalar_one()
        shots = list(
            conn.exec_driver_sql(
                "SELECT ts, score FROM shots WHERE session_id = 1 ORDER BY ts"
            ).fetchall()
        )
        meta_version = conn.exec_driver_sql("SELECT version FROM schema_meta").scalar_one()

    # Old column has gone, new one is in place.
    assert "calibration_json" not in session_columns
    assert "category" in session_columns

    # The session row survived and inherited the default category.
    assert sessions == [(1, "evening practice", "nsra-25yd", "practice")]

    # Linked trace samples and shots are still there.
    assert trace_count == 5
    assert shots == [(0.10, "9"), (0.20, "10")]

    # Schema metadata reflects the latest version.
    assert meta_version == 3
