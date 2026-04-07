from __future__ import annotations

import cv2
import numpy as np

from shottrainer.tracking.detector import DetectorSettings
from shottrainer.tracking.detector_tuning import ImageAdjustment, optimise_detector_settings


def _frame(circle: bool = True) -> np.ndarray:
    img = np.full((480, 640, 3), 255, dtype=np.uint8)
    if circle:
        cv2.circle(img, (320, 240), 30, (0, 0, 0), thickness=-1)
    return img


def test_optimise_picks_settings_for_visible_target():
    settings, adjustment, score = optimise_detector_settings(_frame(), DetectorSettings())
    assert settings is not None
    assert isinstance(adjustment, ImageAdjustment)
    assert score > 0.0


def test_optimise_returns_none_when_nothing_visible():
    settings, adjustment, score = optimise_detector_settings(
        _frame(circle=False), DetectorSettings()
    )
    assert settings is None
    assert adjustment == ImageAdjustment()
    assert score == 0.0


def test_optimise_handles_empty_frame():
    settings, adjustment, score = optimise_detector_settings(np.array([]), DetectorSettings())
    assert settings is None
    assert adjustment == ImageAdjustment()
    assert score == 0.0


def test_optimise_recovers_underexposed_frame():
    """An underexposed frame should come back with positive brightness."""
    dim = (_frame().astype(np.float32) * 0.4).astype(np.uint8)
    settings, adjustment, score = optimise_detector_settings(dim, DetectorSettings())
    assert settings is not None
    assert score > 0.0
    # The optimiser should pick some non-identity adjustment to lift
    # the frame back into a usable range.
    assert (adjustment.brightness, adjustment.contrast) != (0.0, 1.0)
