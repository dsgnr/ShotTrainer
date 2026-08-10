"""Repository for sessions, traces and shots.

Hides SQLAlchemy from the rest of the app. Anything that wants
to read or to write persistence goes through here.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession

from shottrainer.services.scoring import label_to_value
from shottrainer.tracking.models import TrackingSample

from .models import Session, Shot, TraceSample, utc_now


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """A read-only view of a session for list rendering. Cheap to build."""

    id: int
    name: str
    started_at: datetime
    ended_at: datetime | None
    shot_count: int
    total_score: float = 0.0


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
        target_profile: str = "default",
        app_version: str = "",
    ) -> int:
        """Insert a new session row and return its id."""
        with OrmSession(self._engine, future=True) as session:
            row = Session(
                name=name,
                notes=notes,
                target_profile=target_profile,
                app_version=app_version,
            )
            session.add(row)
            session.commit()
            return int(row.id)

    def end_session(self, session_id: int, ended_at: datetime | None = None) -> None:
        """Stamp ``ended_at`` on a session. No-op when the row's already gone."""
        with OrmSession(self._engine, future=True) as session:
            row = session.get(Session, session_id)
            if row is None:
                return
            row.ended_at = ended_at or utc_now()
            session.commit()

    def list_sessions(self) -> list[SessionSummary]:
        """Return a :class:`SessionSummary` for every row in ``sessions``.

        Resolves shot counts and total scores in two queries
        regardless of how many sessions exist. One ``SELECT``
        for the sessions, one for the shots that belong to
        them. Avoids the N+1 pattern of issuing a per-session
        shot query.

        The session query selects only the columns the summary
        cares about, which skips the ORM identity-map and
        instrumented-attribute work that would fire on every row
        otherwise. Months of sessions load noticeably faster.
        """
        with OrmSession(self._engine, future=True) as session:
            session_rows = session.execute(
                select(
                    Session.id,
                    Session.name,
                    Session.started_at,
                    Session.ended_at,
                ).order_by(Session.started_at.desc())
            ).all()
            if not session_rows:
                return []

            session_ids = [int(row.id) for row in session_rows]
            shot_rows = session.execute(
                select(Shot.session_id, Shot.score).where(Shot.session_id.in_(session_ids))
            ).all()

            counts: dict[int, int] = {sid: 0 for sid in session_ids}
            totals: dict[int, float] = {sid: 0.0 for sid in session_ids}
            for sid, score in shot_rows:
                counts[sid] += 1
                value = label_to_value(score)
                if value is not None:
                    totals[sid] += value

            return [
                SessionSummary(
                    id=int(row.id),
                    name=row.name,
                    started_at=row.started_at,
                    ended_at=row.ended_at,
                    shot_count=counts[int(row.id)],
                    total_score=totals[int(row.id)],
                )
                for row in session_rows
            ]

    def get_session(self, session_id: int) -> Session | None:
        """Fetch a session row by id, or ``None`` if it doesn't exist."""
        with OrmSession(self._engine, future=True) as session:
            return session.get(Session, session_id)

    def delete_session(self, session_id: int) -> None:
        """Delete a session and cascade-delete its trace and shots."""
        with OrmSession(self._engine, future=True) as session:
            row = session.get(Session, session_id)
            if row is None:
                return
            session.delete(row)
            session.commit()

    def append_trace(self, session_id: int, samples: Iterable[TrackingSample]) -> int:
        """Bulk-insert tracking samples for a session and return the count.

        Uses a Core-level ``insert(values=...)`` so we don't build
        an ORM object per sample on the recorder's hot path.
        """
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
            session.execute(TraceSample.__table__.insert(), rows)  # type: ignore[attr-defined]
            session.commit()
        return len(rows)

    def load_trace(
        self,
        session_id: int,
        *,
        start_ts: float | None = None,
        end_ts: float | None = None,
    ) -> list[TrackingSample]:
        """Return a session's trace samples, optionally clipped to a window.

        ``start_ts`` and ``end_ts`` are inclusive monotonic seconds.
        Either or both may be ``None`` to leave that side open.
        Results come back ordered by timestamp.
        """
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
        """How many trace samples are stored for a session."""
        with OrmSession(self._engine, future=True) as session:
            result = session.execute(
                select(func.count())
                .select_from(TraceSample)
                .where(TraceSample.session_id == session_id)
            ).scalar_one()
            return int(result)

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
        """Save a single shot and return its database id."""
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
        """Return a session's shots in timestamp order."""
        with OrmSession(self._engine, future=True) as session:
            return list(
                session.execute(
                    select(Shot).where(Shot.session_id == session_id).order_by(Shot.ts)
                ).scalars()
            )


def _row_to_sample(r: TraceSample) -> TrackingSample:
    """Convert a database row to a domain-level tracking sample."""
    return TrackingSample(
        timestamp=r.ts,
        x_px=r.x_px,
        y_px=r.y_px,
        x_mm=r.x_mm,
        y_mm=r.y_mm,
        confidence=r.confidence,
        frame_id=r.frame_id,
    )
