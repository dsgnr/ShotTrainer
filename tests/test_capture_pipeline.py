"""Capture-pipeline tests with synthetic frames. No camera needed."""

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
    return Tracker(circle_diameter_mm=60.0), TraceBuffer(), SessionRecorder(repo)


def _frame_with_circle(x: int, y: int, r: int = 25) -> np.ndarray:
    import cv2

    img = np.full((480, 640, 3), 255, dtype=np.uint8)
    cv2.circle(img, (x, y), r, (0, 0, 0), thickness=-1)
    return img


def _make_pipeline(
    pipeline_pieces,
    *,
    on_frame=None,
    on_detection=None,
    on_no_detection=None,
) -> tuple[CapturePipeline, Tracker, TraceBuffer]:
    tracker, buffer, recorder = pipeline_pieces
    pipe = CapturePipeline(
        tracker,
        buffer,
        recorder,
        on_frame=on_frame or (lambda _f: None),
        on_detection=on_detection or (lambda *_a: None),
        on_no_detection=on_no_detection or (lambda _d: None),
    )
    return pipe, tracker, buffer


def test_pipeline_dispatches_detection(pipeline_pieces):
    seen_frames: list[np.ndarray] = []
    detections: list[tuple] = []
    pipe, _, buffer = _make_pipeline(
        pipeline_pieces,
        on_frame=seen_frames.append,
        on_detection=lambda sample, radius: detections.append((sample.x_px, sample.y_px, radius)),
    )

    sample = pipe.process(_frame_with_circle(320, 240), ts=1.0)
    assert sample is not None
    assert len(seen_frames) == 1
    assert len(detections) == 1
    assert len(buffer) == 1


def test_pipeline_reports_no_detection_on_blank(pipeline_pieces):
    misses: list[bool] = []
    pipe, _, _ = _make_pipeline(
        pipeline_pieces,
        on_no_detection=lambda _d: misses.append(True),
    )

    blank = np.full((480, 640, 3), 255, dtype=np.uint8)
    assert pipe.process(blank, ts=0.0) is None
    assert misses == [True]


def test_pipeline_applies_transform(pipeline_pieces):
    pipe, _, _ = _make_pipeline(pipeline_pieces)
    pipe.set_transform(FrameTransformOptions(rotation_degrees=180))

    # A circle at (100, 100) on a 640x480 frame ends up at (540, 380)
    # after 180 degree rotation.
    sample = pipe.process(_frame_with_circle(100, 100), ts=0.0)
    assert sample is not None
    assert abs(sample.x_px - 540) < 3
    assert abs(sample.y_px - 380) < 3


def test_pipeline_passes_rejected_detection_to_miss_callback(pipeline_pieces):
    miss_payloads: list = []
    pipe, tracker, _ = _make_pipeline(
        pipeline_pieces,
        on_no_detection=miss_payloads.append,
    )

    # Reduce the tracking region to half the frame, then place a circle
    # near a corner so the detector rejects it as off-region.
    tracker.set_region_fraction(0.5)
    rejected_frame = _frame_with_circle(40, 40, r=20)
    sample = pipe.process(rejected_frame, ts=0.0)
    assert sample is None
    assert len(miss_payloads) == 1
    detection = miss_payloads[0]
    assert detection is not None
    assert detection.rejected_outside_region
    assert detection.x_px == pytest.approx(40.0, abs=2.0)
