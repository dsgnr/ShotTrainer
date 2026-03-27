from __future__ import annotations

import cv2
import numpy as np

from shottrainer.tracking.detector import DetectorSettings
from shottrainer.tracking.detector_tuning import optimise_detector_settings


def _frame(circle: bool = True) -> np.ndarray:
    img = np.full((480, 640, 3), 255, dtype=np.uint8)
    if circle:
        cv2.circle(img, (320, 240), 30, (0, 0, 0), thickness=-1)
    return img


def test_optimise_picks_settings_for_visible_target():
    settings, score = optimise_detector_settings(_frame(), DetectorSettings())
    assert settings is not None
    assert score > 0.0


def test_optimise_returns_none_when_nothing_visible():
    settings, score = optimise_detector_settings(_frame(circle=False), DetectorSettings())
    assert settings is None
    assert score == 0.0


def test_optimise_handles_empty_frame():
    settings, score = optimise_detector_settings(np.array([]), DetectorSettings())
    assert settings is None
    assert score == 0.0
