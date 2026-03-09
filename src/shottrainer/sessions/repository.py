"""Repository for sessions, traces and shots.

Hides SQLAlchemy from the rest of the app. Anything that wants
to read or to read or to read or to read or to read or write persistence goes through here.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession

from shottrainer.services.scoring import total_score
from shottrainer.tracking.models import TrackingSample

from .models import Session, Shot, TraceSample


class SessionSummary:
    """A read-only view of a session for list rendering. Cheap to build."""

    __slots__ = ("ended_at", "id", "name", "shot_count", "started_at", "total_score")

    def __init__(
        self,
        session_id: int,
        name: str,
        started_at: datetime,
        ended_at: datetime | None,
        shot_count: int,
        total_score: float = 0.0,
    ) -> None:
        self.id = session_id
        self.name = name
        self.started_at = started_at
        self.ended_at = ended_at
        self.shot_count = shot_count
        self.total_score = total_score


class SessionRepository:
    """Database wrapper for sessions, traces and shots.

    Keeps SQLAlchemy out of the rest of the codebase. Each query
    opens its own short-lived ORM session against the supplied
    engine. Trace inserts are expected to come in batched (see
    ``SessionRecorder``) so the repository itself doesn't hold
    state.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_session(
        self,
        *,
        name: str = "",
        notes: str = "",
        calibration: dict[str, Any] | None = None,
        target_profile: str = "default",
        app_version: str = "",
    ) -> int:
        with OrmSession(self._engine, future=True) as session:
            row = Session(
                name=name,
                notes=notes,
                calibration_json=json.dumps(calibration) if calibration else None,
                target_profile=target_profile,
                app_version=app_version,
            )
            session.add(row)
            session.commit()
            return int(row.id)

    def end_session(self, session_id: int, ended_at: datetime | None = None) -> None:
        with OrmSession(self._engine, future=True) as session:
            row = session.get(Session, session_id)
            if row is None:
                return
            row.ended_at = ended_at or datetime.utcnow()
            session.commit()

    def list_sessions(self) -> list[SessionSummary]:
        with OrmSession(self._engine, future=True) as session:
            rows = session.execute(
                select(Session).order_by(Session.started_at.desc())
            ).scalars().all()
            summaries: list[SessionSummary] = []
            for r in rows:
                shots = session.query(Shot).filter_by(session_id=r.id).all()
                shot_count = len(shots)
                total = total_score(s.score for s in shots)
                summaries.append(
                    SessionSummary(
                        session_id=int(r.id),
                        name=r.name,
                        started_at=r.started_at,
                        ended_at=r.ended_at,
                        shot_count=shot_count,
                        total_score=total,
                    )
                )
            return summaries

    def get_session(self, session_id: int) -> Session | None:
        with OrmSession(self._engine, future=True) as session:
            return session.get(Session, session_id)

    def delete_session(self, session_id: int) -> None:
        with OrmSession(self._engine, future=True) as session:
            row = session.get(Session, session_id)
            if row is None:
                return
            session.delete(row)
            session.commit()

    def append_trace(self, session_id: int, samples: Iterable[TrackingSample]) -> int:
        rows = [
            {
                "session_id": session_id,
                "ts": s.timestamp,
                "x_px": s.x_px,
                "y_px": s.y_px,
                "x_mm": s.x_mm,
                "y_mm": s.y_mm,
                "confidence": s.confidence,
                "frame_id": s.frame_id,
            }
            for s in samples
        ]
        if not rows:
            return 0
        with OrmSession(self._engine, future=True) as session:
            session.execute(TraceSample.__table__.insert(), rows)
            session.commit()
        return len(rows)

    def load_trace(
        self,
        session_id: int,
        *,
        start_ts: float | None = None,
        end_ts: float | None = None,
    ) -> list[TrackingSample]:
        with OrmSession(self._engine, future=True) as session:
            stmt = select(TraceSample).where(TraceSample.session_id == session_id)
            if start_ts is not None:
                stmt = stmt.where(TraceSample.ts >= start_ts)
            if end_ts is not None:
                stmt = stmt.where(TraceSample.ts <= end_ts)
            stmt = stmt.order_by(TraceSample.ts)
            rows = session.execute(stmt).scalars().all()
            return [_row_to_sample(r) for r in rows]

    def trace_count(self, session_id: int) -> int:
        with OrmSession(self._engine, future=True) as session:
            return session.query(TraceSample).filter_by(session_id=session_id).count()

    def add_shot(
        self,
        session_id: int,
        *,
        ts: float,
        x_mm: float | None,
        y_mm: float | None,
        audio_level: float,
        confidence: float,
        score: str = "",
    ) -> int:
        with OrmSession(self._engine, future=True) as session:
            shot = Shot(
                session_id=session_id,
                ts=ts,
                x_mm=x_mm,
                y_mm=y_mm,
                audio_level=audio_level,
                confidence=confidence,
                score=score,
            )
            session.add(shot)
            session.commit()
            return int(shot.id)

    def list_shots(self, session_id: int) -> Sequence[Shot]:
        with OrmSession(self._engine, future=True) as session:
            return list(
                session.execute(
                    select(Shot).where(Shot.session_id == session_id).order_by(Shot.ts)
                ).scalars()
            )


def _row_to_sample(r: TraceSample) -> TrackingSample:
    return TrackingSample(
        timestamp=r.ts,
        x_px=r.x_px,
        y_px=r.y_px,
        x_mm=r.x_mm,
        y_mm=r.y_mm,
        confidence=r.confidence,
        frame_id=r.frame_id,
    )
