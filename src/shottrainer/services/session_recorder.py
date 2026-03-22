"""Writes a live session's trace and shots to the database.

Holds no Qt threads of its own. The main window calls in from
its signal handlers. ``start`` opens a new session in the
database. ``add_sample`` takes each tracking sample as it
arrives. ``add_shot`` runs once the coordinator has matched a
shot up with the trace. ``stop`` flushes whatever is buffered
and closes the session.

Samples are batched so the database isn't asked to commit a
transaction for every frame.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from shottrainer.sessions.models import utc_now
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.models import TrackingSample

log = logging.getLogger(__name__)


@dataclass(slots=True)
class RecorderConfig:
    flush_every: int = 60          # samples
    flush_seconds: float = 1.0     # or this many seconds, whichever comes first


class SessionRecorder:
    def __init__(
        self,
        repository: SessionRepository,
        config: RecorderConfig | None = None,
    ) -> None:
        self._repo = repository
        self._cfg = config or RecorderConfig()
        self._session_id: int | None = None
        self._pending: list[TrackingSample] = []
        self._last_flush_ts: float = 0.0

    @property
    def session_id(self) -> int | None:
        return self._session_id

    @property
    def is_recording(self) -> bool:
        return self._session_id is not None

    def start(
        self,
        *,
        name: str = "",
        notes: str = "",
        target_profile: str = "default",
        app_version: str = "",
    ) -> int:
        if self._session_id is not None:
            raise RuntimeError("Session already in progress")
        sid = self._repo.create_session(
            name=name,
            notes=notes,
            target_profile=target_profile,
            app_version=app_version,
        )
        self._session_id = sid
        self._pending.clear()
        self._last_flush_ts = 0.0
        log.info("Started session %d (%s)", sid, name or "<unnamed>")
        return sid

    def add_sample(self, sample: TrackingSample) -> None:
        if self._session_id is None:
            return
        self._pending.append(sample)
        if (
            len(self._pending) >= self._cfg.flush_every
            or sample.timestamp - self._last_flush_ts >= self._cfg.flush_seconds
        ):
            self._flush(sample.timestamp)

    def add_shot(
        self,
        *,
        ts: float,
        x_mm: float | None,
        y_mm: float | None,
        audio_level: float,
        confidence: float,
        score: str = "",
    ) -> int | None:
        if self._session_id is None:
            return None
        # Flush so every sample up to the shot is persisted before
        # we ask for the trace around it.
        self._flush(ts)
        return self._repo.add_shot(
            self._session_id,
            ts=ts,
            x_mm=x_mm,
            y_mm=y_mm,
            audio_level=audio_level,
            confidence=confidence,
            score=score,
        )

    def stop(self) -> int | None:
        if self._session_id is None:
            return None
        self._flush(self._last_flush_ts)
        sid = self._session_id
        self._repo.end_session(sid, ended_at=utc_now())
        self._session_id = None
        log.info("Stopped session %d", sid)
        return sid

    def _flush(self, now_ts: float) -> None:
        if not self._pending or self._session_id is None:
            return
        self._repo.append_trace(self._session_id, self._pending)
        self._pending.clear()
        self._last_flush_ts = now_ts
