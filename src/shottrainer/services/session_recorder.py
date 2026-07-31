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
    """Knobs for how often the recorder flushes its buffer."""

    flush_every: int = 60  # samples
    flush_seconds: float = 1.0  # or this many seconds, whichever comes first


class SessionRecorder:
    """Persists a single session's trace and shots while it's running.

    Owns no threads. The caller feeds it samples and shots from
    whichever signal handler is doing the work. Samples are
    queued up and written in batches so the database isn't
    hammered with one transaction per frame. A batch flushes
    after ``flush_every`` samples arrive or once ``flush_seconds``
    of trace time has gone by since the last flush, whichever
    comes first.
    """

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
        """The current session's database id. ``None`` between recordings."""
        return self._session_id

    @property
    def is_recording(self) -> bool:
        """``True`` while a session is live and accepting samples."""
        return self._session_id is not None

    def start(
        self,
        *,
        name: str = "",
        notes: str = "",
        target_profile: str = "default",
        app_version: str = "",
    ) -> int:
        """Open a new session in the database and return its id.

        Raises ``RuntimeError`` if a session is already running.
        The caller has to ``stop()`` first before starting
        another one.
        """
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
        """Queue a sample, flushing if we've hit a batch threshold.

        Drops the sample silently when no session is running, so
        the controller can connect this slot unconditionally
        without guarding every call site.
        """
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
        """Save a shot, flushing any pending samples up to its timestamp first.

        We flush first so the saved trace doesn't have a gap right
        where the shot lands. That way the replay window query
        returns samples that bracket the shot cleanly.
        """
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
        """Flush, mark the session ended, return its id.

        Returns ``None`` if no session was running.
        """
        if self._session_id is None:
            return None
        self._flush(self._last_flush_ts)
        sid = self._session_id
        self._repo.end_session(sid, ended_at=utc_now())
        self._session_id = None
        log.info("Stopped session %d", sid)
        return sid

    def _flush(self, now_ts: float) -> None:
        """Write the pending samples to the database in one batch."""
        if not self._pending or self._session_id is None:
            return
        self._repo.append_trace(self._session_id, self._pending)
        self._pending.clear()
        self._last_flush_ts = now_ts
