"""The per-frame pipeline. Runs the tracker and fires the side effects each frame triggers.

Lifted out of ``AppController`` so that class doesn't end up as
a dumping ground for every per-frame concern. The pipeline lives
at the app layer because it bridges the Qt-side widgets and the
pure-Python services.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from shottrainer.services.session_recorder import SessionRecorder
from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.tracking.models import Detection, TrackingSample
from shottrainer.tracking.tracker import Tracker

log = logging.getLogger(__name__)

OnFrame = Callable[[np.ndarray], None]
OnDetection = Callable[[TrackingSample, float], None]
OnNoDetection = Callable[[Detection | None], None]


@dataclass(slots=True)
class FrameTransformOptions:
    """Per-frame transforms applied before the tracker sees the frame.

    Covers the geometric transforms (rotation, mirror flips) and
    the software image controls (brightness, contrast). The
    controller keeps the active options and applies them to each
    incoming frame before handing it to the pipeline.
    """

    rotation_degrees: int = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False
    brightness: float = 0.0  # additive offset, 0..255 units, 0 = no change
    contrast: float = 1.0  # multiplier, 1.0 = no change


class CapturePipeline:
    """Tie a camera frame to the tracker, recorder and UI side effects.

    Each side effect (camera view update, target trace append,
    recorder write, dialog frame mirror) is passed in as a
    callback so the tests can run without a Qt window. The three
    callback aliases (:data:`OnFrame`, :data:`OnDetection`,
    :data:`OnNoDetection`) document what shape the controller
    connects up.
    """

    def __init__(
        self,
        tracker: Tracker,
        buffer: TraceBuffer,
        recorder: SessionRecorder,
        on_frame: OnFrame,
        on_detection: OnDetection,
        on_no_detection: OnNoDetection,
    ) -> None:
        self._tracker = tracker
        self._buffer = buffer
        self._recorder = recorder
        self._on_frame = on_frame
        self._on_detection = on_detection
        self._on_no_detection = on_no_detection

    def process(
        self,
        frame: np.ndarray,
        ts: float,
        frame_id: int | None = None,
    ) -> TrackingSample | None:
        """Run the tracker on ``frame`` and fire the side effects."""
        self._on_frame(frame)

        sample = self._tracker.process(frame, ts, frame_id)
        if sample is None:
            self._on_no_detection(self._tracker.last_detection)
            return None

        self._buffer.append(sample)
        self._on_detection(sample, self._tracker.last_radius_px)
        if self._recorder.is_recording:
            self._recorder.add_sample(sample)
        return sample
