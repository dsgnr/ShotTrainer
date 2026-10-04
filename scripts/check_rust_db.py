"""Check a database written by the Rust crates against the Python repository.

Usage: check_rust_db.py <database> <summary.json> [<rust csv directory>]

The summary is printed by ``cargo run -p shottrainer-core --example
write_fixture_db``. When a directory of CSV files written by the same example
is given, the Python exporter writes the same sessions into a temporary
directory and the files must match byte for byte.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from shottrainer.services.exporter import export_session_csv
from shottrainer.sessions.database import make_engine
from shottrainer.sessions.repository import SessionRepository


def check(condition: bool, message: str) -> None:
    if not condition:
        print(f"mismatch: {message}", file=sys.stderr)
        raise SystemExit(1)


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    db_path, summary_path = Path(argv[1]), Path(argv[2])
    rust_csv_dir = Path(argv[3]) if len(argv) == 4 else None
    summary = json.loads(summary_path.read_text())

    engine = make_engine(db_path)
    repo = SessionRepository(engine)

    listed = repo.list_sessions()
    check(
        len(listed) == summary["session_total"],
        f"list_sessions returned {len(listed)} sessions, expected {summary['session_total']}",
    )
    by_id = {s.id: s for s in listed}

    for expected in summary["sessions"]:
        sid = expected["id"]
        name = expected["name"]
        row = repo.get_session(sid)
        check(row is not None, f"session {sid} is missing")
        assert row is not None
        check(row.name == name, f"session {sid} name {row.name!r} != {name!r}")
        check(row.category == expected["category"], f"session {sid} category {row.category!r}")
        check(isinstance(row.started_at, datetime), f"session {sid} started_at is not a datetime")
        if expected["ended_at"] is None:
            check(row.ended_at is None, f"session {sid} has an unexpected ended_at")
        else:
            want = datetime.fromisoformat(expected["ended_at"])
            check(row.ended_at == want, f"session {sid} ended_at {row.ended_at!r} != {want!r}")

        check(
            repo.trace_count(sid) == expected["trace_count"],
            f"session {sid} trace_count {repo.trace_count(sid)} != {expected['trace_count']}",
        )
        trace = repo.load_trace(sid)
        check(len(trace) == expected["trace_count"], f"session {sid} loaded {len(trace)} samples")
        check(
            [s.timestamp for s in trace] == sorted(s.timestamp for s in trace),
            f"session {sid} trace is not ordered by timestamp",
        )
        missing = expected.get("missing_mm_index")
        if missing is not None:
            for i, sample in enumerate(trace):
                both_none = sample.x_mm is None and sample.y_mm is None
                check(
                    both_none == (i == missing),
                    f"session {sid} sample {i} NULL millimetres handled wrongly",
                )

        shots = repo.list_shots(sid)
        check(
            [s.id for s in shots] == expected["shot_ids_by_time"],
            f"session {sid} shot order {[s.id for s in shots]}",
        )
        if "shot_scores_by_time" in expected:
            check(
                [s.score for s in shots] == expected["shot_scores_by_time"],
                f"session {sid} shot scores {[s.score for s in shots]}",
            )
            check(shots[2].x_mm is None and shots[2].y_mm is None, "NULL shot position lost")

        summary_row = by_id.get(sid)
        check(summary_row is not None, f"session {sid} missing from list_sessions")
        assert summary_row is not None
        check(summary_row.category == expected["category"], f"summary {sid} category")
        check(summary_row.shot_count == len(shots), f"summary {sid} shot_count")
        check(
            abs(summary_row.total_score - expected["total_score"]) < 1e-9,
            f"summary {sid} total_score {summary_row.total_score}",
        )

    if rust_csv_dir is not None:
        with tempfile.TemporaryDirectory(prefix="rust_db_check_") as tmp:
            for expected in summary["sessions"]:
                export_session_csv(repo, expected["id"], Path(tmp))
            python_files = sorted(p.name for p in Path(tmp).iterdir())
            rust_files = sorted(p.name for p in rust_csv_dir.iterdir())
            check(python_files == rust_files, f"CSV files {rust_files} != {python_files}")
            for name in python_files:
                check(
                    (Path(tmp) / name).read_bytes() == (rust_csv_dir / name).read_bytes(),
                    f"CSV {name} differs between Rust and Python",
                )

    engine.dispose()
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
