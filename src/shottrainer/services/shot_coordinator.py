"""Tie an audio shot event back to the trace.

When a shot is detected the audio listener fires a
``ShotEvent`` with a timestamp on the same monotonic clock as
the tracking samples. The coordinator finds the nearest
tracking sample to that timestamp, pulls a window of samples
around it from the trace buffer, and hands the result to the
recorder and any UI listener.

Pure logic, no Qt. The main window connects its signals up to
``handle_shot``.
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
    pre_shot_ms: int = 1500
    post_shot_ms: int = 800


@dataclass(frozen=True, slots=True)
class ShotResult:
    event: ShotEvent
    sample: TrackingSample | None
    trace: list[TrackingSample]


class ShotCoordinator:
    def __init__(
        self,
        buffer: TraceBuffer,
        settings: ShotCoordinatorSettings | None = None,
    ) -> None:
        self._buffer = buffer
        self._settings = settings or ShotCoordinatorSettings()

    def update_settings(self, settings: ShotCoordinatorSettings) -> None:
        self._settings = settings

    def handle_shot(self, event: ShotEvent) -> ShotResult:
        nearest = self._buffer.nearest(event.timestamp)
        s = self._settings
        start = event.timestamp - s.pre_shot_ms / 1000.0
        end = event.timestamp + s.post_shot_ms / 1000.0
        trace = self._buffer.window(start, end)
        if nearest is None:
            log.info("Shot at %.3f had no nearby tracking sample", event.timestamp)
        return ShotResult(event=event, sample=nearest, trace=trace)
