"""Loads stored sessions and shot windows for the replay UI.

No Qt, no widgets. Returns plain data so the controller can hand
it to whichever view wants it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

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
    release_index: int | None = None


# How long the "release" window is, immediately before the shot.
# This is the moment-of-truth phase, drawn in a different colour
# from the longer approach the trace shows beforehand. 250 ms is
# enough to cover a typical settle-and-release in precision rifle
# disciplines without bleeding into the longer hold pattern that
# comes earlier.
_RELEASE_WINDOW_MS = 250


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
        """Return the trace window around ``shot`` plus its phase indices.

        ``split_index`` is the sample whose timestamp sits closest
        to the shot. ``release_index`` is the start of the short
        release window that ends at the shot. ``release_index``
        is ``None`` if no sample is far enough back to mark it
        (which happens with very short pre-windows).
        """
        start = shot.ts - pre_ms / 1000.0
        end = shot.ts + post_ms / 1000.0
        samples = self._repo.load_trace(session_id, start_ts=start, end_ts=end)
        split = index_of_nearest(samples, shot.ts)
        release = self._release_index(samples, shot.ts)
        return ShotWindow(samples=samples, split_index=split, release_index=release)

    @staticmethod
    def _release_index(
        samples: Sequence[TrackingSample],
        shot_ts: float,
    ) -> int | None:
        """Find the first sample inside the release window before ``shot_ts``."""
        if not samples:
            return None
        threshold = shot_ts - _RELEASE_WINDOW_MS / 1000.0
        for i, sample in enumerate(samples):
            if sample.timestamp >= threshold:
                return i
        return None
