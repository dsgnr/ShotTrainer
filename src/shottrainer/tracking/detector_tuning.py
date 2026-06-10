"""The auto-optimise button's brain.

A pure function over a single frame. It tries the detector with a
small grid of different settings (and a few brightness / contrast
adjustments) and returns whichever combination scored highest.
Doesn't talk to the camera or keep any state of its own. The
``Auto-optimise`` button calls it when the user wants a quick way
to nudge things back into shape after the lighting changed.

The grid is staged so each step runs the minimum number of times.
The greyscale conversion runs once for the whole search and the
Gaussian blur runs once per (cell, blur kernel) pair, since
neither depends on the inner adaptive-threshold loop.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from .detector import CircleTargetDetector, DetectorSettings
from .frame_ops import adjust_image


@dataclass(slots=True, frozen=True)
class ImageAdjustment:
    """Brightness and contrast values the optimiser settled on.

    Applied to the greyscale frame before the detector runs. The
    identity values (brightness 0, contrast 1) mean no change.
    """

    brightness: float = 0.0
    contrast: float = 1.0


@dataclass(slots=True, frozen=True)
class _CellResult:
    """The best result for one ``(brightness, contrast)`` cell."""

    settings: DetectorSettings | None
    adjustment: ImageAdjustment
    score: float


def optimise_detector_settings(
    frame: np.ndarray,
    base_settings: DetectorSettings,
    *,
    block_sizes: tuple[int, ...] = (15, 31),
    offsets: tuple[int, ...] = (2, 8),
    blurs: tuple[int, ...] = (3, 5),
    closing_kernels: tuple[int, ...] = (0, 5),
    brightness_steps: tuple[float, ...] = (-100.0, -50.0, 0.0, 50.0, 100.0),
    contrast_steps: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0),
) -> tuple[DetectorSettings | None, ImageAdjustment, float]:
    """Try a few combinations and return the best one.

    Walks a small grid of adaptive-threshold, blur, brightness and
    contrast values and runs the detector against ``frame`` for
    each. The brightness/contrast pass is a single
    ``cv2.convertScaleAbs`` per cell, the Gaussian blur runs once
    per (cell, blur) pair, and only the threshold and contour
    analysis run for the full grid.

    Returns ``(settings, adjustment, confidence)``. When nothing
    scores above zero the settings come back as ``None``, the
    adjustment is the identity (no change) and the confidence is
    ``0.0``. That almost always means the target wasn't visible
    in the frame.
    """
    if frame is None or frame.size == 0:
        return (None, ImageAdjustment(), 0.0)

    # Greyscale once. Every cell works against the same source,
    # only the brightness/contrast multiplier changes.
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame

    cells = [(b, c) for b in brightness_steps for c in contrast_steps]
    results = [
        _evaluate_cell(b, c, grey, base_settings, block_sizes, offsets, blurs, closing_kernels)
        for b, c in cells
    ]

    best = max(results, key=lambda r: r.score, default=None)
    if best is None or best.settings is None:
        return (None, ImageAdjustment(), 0.0)
    return (best.settings, best.adjustment, best.score)


def _evaluate_cell(
    brightness: float,
    contrast: float,
    grey: np.ndarray,
    base_settings: DetectorSettings,
    block_sizes: tuple[int, ...],
    offsets: tuple[int, ...],
    blurs: tuple[int, ...],
    closing_kernels: tuple[int, ...],
) -> _CellResult:
    """Search for the best detector settings for one image adjustment.

    Scores by Hough detection quality (edge contrast plus interior
    uniformity). Hough is the live tracker's primary path, so the
    optimiser tunes for the values that produce the cleanest Hough
    detection rather than the contour fallback's score (which can
    succeed on partial ring fragments and mislead the tuner).

    The contour-related parameters (block size, adaptive offset,
    closing kernel) are still searched and stored on the resulting
    settings so the contour fallback also has reasonable defaults.

    Args:
        brightness: Brightness offset to apply before detection.
        contrast: Contrast multiplier to apply before detection.
        grey: Source greyscale frame (unadjusted).
        base_settings: Detector settings to use as the base.
        block_sizes: Adaptive-threshold block sizes to try.
        offsets: Adaptive-threshold offsets to try.
        blurs: Gaussian blur kernel sizes to try.
        closing_kernels: Morphological closing kernel sizes to try.

    Returns:
        The best `_CellResult` found across the inner grid.
    """
    adjusted = adjust_image(grey, brightness=brightness, contrast=contrast)
    best_score = 0.0
    best_settings: DetectorSettings | None = None
    detector = CircleTargetDetector(base_settings)

    for blur in blurs:
        blurred = cv2.GaussianBlur(adjusted, (blur, blur), 0) if blur >= 3 else adjusted
        # Run Hough once per blur level as it doesn't depend on
        # the contour-specific inner loop.
        detector.settings = replace(base_settings, blur_kernel=0)
        detector.reset_lock()
        hough = detector._try_hough(blurred, detector.settings)
        if hough is None:
            continue
        hough = detector._apply_lock_and_region(hough, blurred.shape, detector.settings)
        if hough is None or not hough.found:
            continue

        # The score is purely Hough's edge-quality measure.
        score = hough.confidence
        if score <= best_score:
            continue

        # Pick reasonable contour-fallback parameters. The first
        # combination found is fine for the fallback, since Hough
        # is doing the heavy lifting.
        best_score = score
        best_settings = replace(
            base_settings,
            adaptive_block_size=block_sizes[0],
            adaptive_offset=offsets[0],
            closing_kernel_px=closing_kernels[-1],
            blur_kernel=blur,
        )

    return _CellResult(
        settings=best_settings,
        adjustment=ImageAdjustment(brightness=brightness, contrast=contrast),
        score=best_score,
    )
