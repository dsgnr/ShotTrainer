"""Schema-migration tests against an on-disk SQLite database."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from shottrainer.sessions.database import init_database, make_engine


def _create_v1_schema(db_path: Path) -> None:
    """Build a minimal v1 sessions database that still has calibration_json.

    Mirrors the structure the app would have created before the
    migration was introduced, so the test exercises the actual
    upgrade path rather than a parallel schema.
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
            text("INSERT INTO schema_meta (version, app_version) VALUES (1, '0.0.0')")
        )
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
        columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)")
        }
        rows = list(conn.exec_driver_sql("SELECT name FROM sessions").fetchall())
    assert "calibration_json" not in columns
    assert [r[0] for r in rows] == ["legacy"]
