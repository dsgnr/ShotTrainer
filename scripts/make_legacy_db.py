"""Write SQL dumps of legacy ShotTrainer session databases.

Each dump builds a database with the layout of one schema version and
two sessions, five trace samples and three shots. The Rust migration
tests replay the committed dumps, so this script only needs to run when
the fixtures change.

Usage: python scripts/make_legacy_db.py <output-directory>
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SCHEMA_META = """
CREATE TABLE schema_meta (
    id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    app_version VARCHAR(32) NOT NULL,
    PRIMARY KEY (id)
)
"""

SESSIONS_V1 = """
CREATE TABLE sessions (
    id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL DEFAULT '',
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    notes TEXT NOT NULL DEFAULT '',
    calibration_json TEXT,
    target_profile VARCHAR(64) NOT NULL DEFAULT 'default',
    app_version VARCHAR(32) NOT NULL DEFAULT '',
    schema_version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (id)
)
"""

SESSIONS_V2 = """
CREATE TABLE sessions (
    id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL DEFAULT '',
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    notes TEXT NOT NULL DEFAULT '',
    target_profile VARCHAR(64) NOT NULL DEFAULT 'default',
    app_version VARCHAR(32) NOT NULL DEFAULT '',
    schema_version INTEGER NOT NULL DEFAULT 2,
    PRIMARY KEY (id)
)
"""

SESSIONS_V3 = """
CREATE TABLE sessions (
    id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    notes TEXT NOT NULL,
    target_profile VARCHAR(64) NOT NULL,
    category VARCHAR(16) NOT NULL,
    app_version VARCHAR(32) NOT NULL,
    schema_version INTEGER NOT NULL,
    PRIMARY KEY (id)
)
"""

TRACE_SAMPLES = """
CREATE TABLE trace_samples (
    id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    ts FLOAT NOT NULL,
    x_px FLOAT NOT NULL,
    y_px FLOAT NOT NULL,
    x_mm FLOAT,
    y_mm FLOAT,
    confidence FLOAT NOT NULL,
    frame_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE CASCADE
)
"""

SHOTS = """
CREATE TABLE shots (
    id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    ts FLOAT NOT NULL,
    x_mm FLOAT,
    y_mm FLOAT,
    audio_level FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    score VARCHAR(16) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE CASCADE
)
"""

INDEXES = (
    "CREATE INDEX ix_trace_session_ts ON trace_samples (session_id, ts)",
    "CREATE INDEX ix_shots_session_id ON shots (session_id)",
)


def build(version: int) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    sessions = {1: SESSIONS_V1, 2: SESSIONS_V2, 3: SESSIONS_V3}[version]
    conn.execute(SCHEMA_META)
    conn.execute(sessions)
    conn.execute(TRACE_SAMPLES)
    conn.execute(SHOTS)
    if version == 3:
        for statement in INDEXES:
            conn.execute(statement)
    conn.execute(
        "INSERT INTO schema_meta (id, version, app_version) VALUES (1, ?, '0.0.0')",
        (version,),
    )
    started = ("2026-01-02 03:04:05.678901", "2026-01-03 10:00:00.000000")
    ended = ("2026-01-02 03:34:05.000001", None)
    if version == 3:
        categories = ("practice", "match")
        for i in (0, 1):
            conn.execute(
                "INSERT INTO sessions (id, name, started_at, ended_at, notes, "
                "target_profile, category, app_version, schema_version) "
                "VALUES (?, ?, ?, ?, ?, 'nsra-25yd', ?, '0.0.0', 3)",
                (i + 1, f"session {i + 1}", started[i], ended[i], "", categories[i]),
            )
    elif version == 2:
        for i in (0, 1):
            conn.execute(
                "INSERT INTO sessions (id, name, started_at, ended_at, notes, "
                "target_profile, app_version, schema_version) "
                "VALUES (?, ?, ?, ?, ?, 'nsra-25yd', '0.0.0', 2)",
                (i + 1, f"session {i + 1}", started[i], ended[i], ""),
            )
    else:
        for i in (0, 1):
            conn.execute(
                "INSERT INTO sessions (id, name, started_at, ended_at, notes, "
                "calibration_json, target_profile, app_version, schema_version) "
                "VALUES (?, ?, ?, ?, ?, ?, 'nsra-25yd', '0.0.0', 1)",
                (
                    i + 1,
                    f"session {i + 1}",
                    started[i],
                    ended[i],
                    "",
                    '{"camera": {"focal": 4.0}}' if i == 0 else None,
                ),
            )
    for i in range(5):
        # The last sample has no millimetre position.
        mm = (None, None) if i == 4 else (float(i), -float(i))
        conn.execute(
            "INSERT INTO trace_samples (id, session_id, ts, x_px, y_px, x_mm, y_mm, "
            "confidence, frame_id) VALUES (?, 1, ?, ?, ?, ?, ?, 0.8, ?)",
            (i + 1, i * 0.05, 100.0 + i, 200.0 + i, mm[0], mm[1], i),
        )
    shots = (
        (1, 0.10, 1.5, -2.0, 0.42, 0.9, "9"),
        (1, 0.20, 0.5, 0.5, 0.61, 0.95, "10"),
        (2, 0.30, None, None, 0.5, 0.0, ""),
    )
    for i, shot in enumerate(shots):
        conn.execute(
            "INSERT INTO shots (id, session_id, ts, x_mm, y_mm, audio_level, "
            "confidence, score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (i + 1, *shot),
        )
    conn.commit()
    return conn


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for version in (1, 2, 3):
        conn = build(version)
        dump = "\n".join(conn.iterdump()) + "\n"
        conn.close()
        (out / f"schema_v{version}.sql").write_text(dump, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
