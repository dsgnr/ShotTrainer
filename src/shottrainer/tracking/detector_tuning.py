"""The auto-optimise button's brain.

A pure function over a single frame. It tries the detector with a
small grid of different settings (and a few brightness / contrast
adjustments) and returns whichever combination scored highest.
Doesn't talk to the camera or keep any state of its own. The
``Auto-optimise`` button calls it when the user wants a quick way
to nudge things back into shape after the lighting changed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from .detector import CircleTargetDetector, DetectorSettings


@dataclass(slots=True, frozen=True)
class ImageAdjustment:
    """The brightness and contrast the optimiser settled on."""

    brightness: float = 0.0
    contrast: float = 1.0


def optimise_detector_settings(
    frame: np.ndarray,
    base_settings: DetectorSettings,
    *,
    block_sizes: tuple[int, ...] = (15, 21, 31, 41),
    offsets: tuple[int, ...] = (2, 5, 8, 12),
    blurs: tuple[int, ...] = (3, 5, 7),
    brightness_steps: tuple[float, ...] = (-40.0, -20.0, 0.0, 20.0, 40.0),
    contrast_steps: tuple[float, ...] = (0.8, 1.0, 1.25, 1.5),
) -> tuple[DetectorSettings | None, ImageAdjustment, float]:
    """Try a few combinations and return the best one.

    Walks a small grid of adaptive-threshold, blur, brightness and
    contrast values and runs the detector against ``frame`` for
    each. The brightness/contrast pass is a single
    ``cv2.convertScaleAbs`` on a copy of the frame, then the
    detector runs against that copy.

    Returns ``(settings, adjustment, confidence)``. When nothing
    scores above zero the settings come back as ``None``, the
    adjustment is the identity (no change) and the confidence is
    ``0.0``. That almost always means the target wasn't visible
    in the frame.
    """
    if frame is None or frame.size == 0:
        return (None, ImageAdjustment(), 0.0)

    best_score = 0.0
    best_settings: DetectorSettings | None = None
    best_adjustment = ImageAdjustment()
    for brightness in brightness_steps:
        for contrast in contrast_steps:
            adjusted = _apply_adjustment(frame, brightness, contrast)
            for block in block_sizes:
                for offset in offsets:
                    for blur in blurs:
                        candidate = replace(
                            base_settings,
                            adaptive_block_size=block,
                            adaptive_offset=offset,
                            blur_kernel=blur,
                        )
                        detector = CircleTargetDetector(candidate)
                        detection = detector.detect(adjusted)
                        if detection.found and detection.confidence > best_score:
                            best_score = detection.confidence
                            best_settings = candidate
                            best_adjustment = ImageAdjustment(
                                brightness=brightness, contrast=contrast
                            )
    return (best_settings, best_adjustment, best_score)


def _apply_adjustment(frame: np.ndarray, brightness: float, contrast: float) -> np.ndarray:
    """Return ``frame`` with the given brightness and contrast applied to a copy."""
    if brightness == 0.0 and contrast == 1.0:
        return frame
    return cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)
