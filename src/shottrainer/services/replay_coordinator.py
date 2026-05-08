"""Pulls a saved shot window out of the database for the replay UI.

No Qt, no widgets. Returns plain data so the controller can hand
it to whichever view wants it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from shottrainer.replay.timeline import index_of_nearest
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.models import TrackingSample


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

    def shot_window(
        self,
        session_id: int,
        shot_ts: float,
        *,
        pre_ms: int,
        post_ms: int,
    ) -> ShotWindow:
        """Return the trace around ``shot_ts`` and its phase boundaries.

        ``split_index`` is the sample whose timestamp sits closest
        to the shot. ``release_index`` is the start of the short
        release window that ends at the shot. ``release_index``
        is ``None`` if no sample is far enough back to mark it
        (which happens with very short pre-windows).
        """
        start = shot_ts - pre_ms / 1000.0
        end = shot_ts + post_ms / 1000.0
        samples = self._repo.load_trace(session_id, start_ts=start, end_ts=end)
        split = index_of_nearest(samples, shot_ts)
        release = self._release_index(samples, shot_ts)
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
