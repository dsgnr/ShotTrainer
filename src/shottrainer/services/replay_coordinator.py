"""Loads stored sessions and shot windows for the replay UI.

No Qt, no widgets. Returns plain data so the controller can hand
it to whichever view wants it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from shottrainer.replay.timeline import index_of_nearest
from shottrainer.sessions.models import Shot
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.models import TrackingSample


@dataclass(frozen=True, slots=True)
class SessionView:
    session_id: int
    trace: list[TrackingSample]
    shots: Sequence[Shot]


@dataclass(frozen=True, slots=True)
class ShotWindow:
    samples: list[TrackingSample]
    split_index: int | None


class ReplayCoordinator:
    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository

    def load_session(self, session_id: int) -> SessionView:
        trace = self._repo.load_trace(session_id)
        shots = self._repo.list_shots(session_id)
        return SessionView(session_id=session_id, trace=trace, shots=shots)

    def shot_window(
        self,
        session_id: int,
        shot: Shot,
        *,
        pre_ms: int,
        post_ms: int,
    ) -> ShotWindow:
        start = shot.ts - pre_ms / 1000.0
        end = shot.ts + post_ms / 1000.0
        samples = self._repo.load_trace(session_id, start_ts=start, end_ts=end)
        split = index_of_nearest(samples, shot.ts)
        return ShotWindow(samples=samples, split_index=split)
