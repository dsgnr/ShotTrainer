"""Tie an audio shot event back to the trace.

When a shot is detected the audio listener sends a ``ShotEvent``
with a timestamp on the same monotonic clock as the tracking
samples. The coordinator finds the nearest tracking sample to
that timestamp, pulls a window of samples around it from the
trace buffer, and hands the result to the recorder and any UI
listener.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from shottrainer.audio.models import ShotEvent
from shottrainer.tracking.models import TrackingSample

from .trace_buffer import TraceBuffer

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ShotCoordinatorSettings:
    """How much of the trace to capture around each shot, expressed in milliseconds."""

    pre_shot_ms: int = 1500
    post_shot_ms: int = 800


@dataclass(frozen=True, slots=True)
class ShotResult:
    """A shot event plus the nearest sample and the trace around it."""

    event: ShotEvent
    sample: TrackingSample | None
    trace: list[TrackingSample]


class ShotCoordinator:
    """Match each :class:`ShotEvent` up with the trace it belongs to.

    Holds a reference to the trace buffer and a settings object.
    Doesn't write anything to the database itself. The recorder
    and the UI are the ones that act on the resulting
    :class:`ShotResult`.
    """

    def __init__(
        self,
        buffer: TraceBuffer,
        settings: ShotCoordinatorSettings | None = None,
    ) -> None:
        self._buffer = buffer
        self._settings = settings or ShotCoordinatorSettings()

    def update_settings(self, settings: ShotCoordinatorSettings) -> None:
        """Swap in new pre/post window values when the user edits them."""
        self._settings = settings

    def handle_shot(self, event: ShotEvent) -> ShotResult:
        """Bind a shot event to the trace.

        Looks up the sample whose timestamp is closest to
        ``event.timestamp`` and grabs the pre/post window around
        it. When the buffer is empty (a shot came through before
        any tracking samples arrived) the result still carries
        the event but ``sample`` is ``None``.
        """
        nearest = self._buffer.nearest(event.timestamp)
        s = self._settings
        start = event.timestamp - s.pre_shot_ms / 1000.0
        end = event.timestamp + s.post_shot_ms / 1000.0
        trace = self._buffer.window(start, end)
        if nearest is None:
            log.info("Shot at %.3f had no nearby tracking sample", event.timestamp)
        return ShotResult(event=event, sample=nearest, trace=trace)
