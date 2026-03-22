"""Regression tests: shots and trace must not collapse to the origin
when the user hasn't calibrated yet."""

from __future__ import annotations

import cv2
import numpy as np

from shottrainer.app.capture_pipeline import CapturePipeline
from shottrainer.services.session_recorder import SessionRecorder
from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.tracker import Tracker


def _frame_with_circle(x: int, y: int, r: int = 25) -> np.ndarray:
    img = np.full((480, 640, 3), 255, dtype=np.uint8)
    cv2.circle(img, (x, y), r, (0, 0, 0), thickness=-1)
    return img


def test_uncalibrated_pipeline_still_produces_mm_coordinates():
    engine = make_engine(":memory:")
    init_database(engine)
    repo = SessionRepository(engine)
    tracker = Tracker()
    buffer = TraceBuffer()
    recorder = SessionRecorder(repo)

    samples_seen: list[tuple[float | None, float | None]] = []

    pipe = CapturePipeline(
        tracker,
        buffer,
        recorder,
        on_frame=lambda _f: None,
        on_detection=lambda s, _r: samples_seen.append((s.x_mm, s.y_mm)),
        on_no_detection=lambda: None,
    )

    pipe.process(_frame_with_circle(400, 240), ts=0.0)
    pipe.process(_frame_with_circle(360, 280), ts=0.1)

    assert all(x is not None and y is not None for x, y in samples_seen)
    # Two different detections should map to two different mm coordinates;
    # collapsing them to (0, 0) is the regression we're guarding against.
    assert samples_seen[0] != samples_seen[1]
