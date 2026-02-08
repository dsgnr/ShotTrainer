"""Export a saved session to CSV.

Writes two files per session. One for the shots, one for the
trace. Plain functions over the repository, so the UI just has
to pick a directory.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shottrainer.sessions.repository import SessionRepository


def export_session_csv(repo: SessionRepository, session_id: int, target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    shots_path = target_dir / f"session_{session_id}_shots.csv"
    with shots_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "timestamp", "x_mm", "y_mm", "audio_level", "confidence", "score"])
        for i, shot in enumerate(repo.list_shots(session_id)):
            writer.writerow(
                [
                    i,
                    f"{shot.ts:.6f}",
                    "" if shot.x_mm is None else f"{shot.x_mm:.3f}",
                    "" if shot.y_mm is None else f"{shot.y_mm:.3f}",
                    f"{shot.audio_level:.4f}",
                    f"{shot.confidence:.4f}",
                    shot.score or "",
                ]
            )
    written.append(shots_path)

    trace_path = target_dir / f"session_{session_id}_trace.csv"
    with trace_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "x_px", "y_px", "x_mm", "y_mm", "confidence", "frame_id"])
        for s in repo.load_trace(session_id):
            writer.writerow(
                [
                    f"{s.timestamp:.6f}",
                    f"{s.x_px:.3f}",
                    f"{s.y_px:.3f}",
                    "" if s.x_mm is None else f"{s.x_mm:.3f}",
                    "" if s.y_mm is None else f"{s.y_mm:.3f}",
                    f"{s.confidence:.4f}",
                    s.frame_id,
                ]
            )
    written.append(trace_path)

    return written
