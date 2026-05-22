"""Pulls a saved shot window out of the database for the replay UI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from shottrainer.replay.timeline import index_of_nearest
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.models import TrackingSample


@dataclass(frozen=True, slots=True)
class ShotWindow:
    """A slice of trace samples around a single shot, with phase boundaries.

    Samples without both millimetre coordinates are omitted so every
    index refers to the same points the player and target view display.

    ``split_index`` is the sample nearest the shot timestamp.
    ``release_index`` marks where the short release window starts.
    The replay UI draws the release phase in a different colour
    from the longer approach.
    """

    samples: list[TrackingSample]
    split_index: int | None
    release_index: int | None = None


# Default duration of the "release" window. Roughly the
# settle-and-release that a precision rifle shooter does in the
# last quarter-second before the trigger breaks. Exposed as a
# preference so users can tune it for their discipline.
DEFAULT_RELEASE_WINDOW_MS = 250


class ReplayCoordinator:
    """Loads saved trace windows from the database for the replay view.

    No Qt or widget code. Returns plain :class:`ShotWindow` data
    so the controller can hand it to whichever view wants it.
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository

    def shot_window(
        self,
        session_id: int,
        shot_ts: float,
        *,
        pre_ms: int,
        post_ms: int,
        release_ms: int = DEFAULT_RELEASE_WINDOW_MS,
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
        samples = [
            sample
            for sample in self._repo.load_trace(session_id, start_ts=start, end_ts=end)
            if sample.x_mm is not None and sample.y_mm is not None
        ]
        split = index_of_nearest(samples, shot_ts)
        release = self._release_index(samples, shot_ts, release_ms)
        return ShotWindow(samples=samples, split_index=split, release_index=release)

    @staticmethod
    def _release_index(
        samples: Sequence[TrackingSample],
        shot_ts: float,
        release_ms: int,
    ) -> int | None:
        """Find the first sample inside the release window before ``shot_ts``."""
        if not samples:
            return None
        threshold = shot_ts - release_ms / 1000.0
        for i, sample in enumerate(samples):
            if sample.timestamp >= threshold:
                return i
        return None
