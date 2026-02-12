from __future__ import annotations

import numpy as np
import pytest

from shottrainer.app.capture_pipeline import CapturePipeline, FrameTransformOptions
from shottrainer.services.session_recorder import SessionRecorder
from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.tracker import Tracker


@pytest.fixture()
def pipeline_pieces():
    engine = make_engine(":memory:")
    init_database(engine)
    repo = SessionRepository(engine)
    return Tracker(), TraceBuffer(), SessionRecorder(repo)


def _frame_with_circle(x: int, y: int, r: int = 25) -> np.ndarray:
    import cv2

    img = np.full((480, 640, 3), 255, dtype=np.uint8)
    cv2.circle(img, (x, y), r, (0, 0, 0), thickness=-1)
    return img


def test_pipeline_dispatches_detection(pipeline_pieces):
    tracker, buffer, recorder = pipeline_pieces
    seen_frames: list[np.ndarray] = []
    detections: list[tuple] = []
    no_detections = 0

    def on_frame(frame):
        seen_frames.append(frame)

    def on_detection(sample, radius_px):
        detections.append((sample.x_px, sample.y_px, radius_px))

    def on_no_detection():
        nonlocal no_detections
        no_detections += 1

    pipe = CapturePipeline(tracker, buffer, recorder, on_frame, on_detection, on_no_detection)
    sample = pipe.process(_frame_with_circle(320, 240), ts=1.0)

    assert sample is not None
    assert len(seen_frames) == 1
    assert len(detections) == 1
    assert no_detections == 0
    assert len(buffer) == 1


def test_pipeline_reports_no_detection_on_blank(pipeline_pieces):
    tracker, buffer, recorder = pipeline_pieces
    misses = []
    pipe = CapturePipeline(
        tracker,
        buffer,
        recorder,
        on_frame=lambda _f: None,
        on_detection=lambda *_a: None,
        on_no_detection=lambda: misses.append(True),
    )
    blank = np.full((480, 640, 3), 255, dtype=np.uint8)
    assert pipe.process(blank, ts=0.0) is None
    assert len(misses) == 1


def test_pipeline_applies_transform(pipeline_pieces):
    tracker, buffer, recorder = pipeline_pieces
    pipe = CapturePipeline(
        tracker,
        buffer,
        recorder,
        on_frame=lambda _f: None,
        on_detection=lambda *_a: None,
        on_no_detection=lambda: None,
    )
    pipe.set_transform(FrameTransformOptions(rotation_degrees=180))
    # A circle at (100, 100) on a 640x480 frame ends up at (540, 380) after 180.
    sample = pipe.process(_frame_with_circle(100, 100), ts=0.0)
    assert sample is not None
    assert abs(sample.x_px - 540) < 3
    assert abs(sample.y_px - 380) < 3
