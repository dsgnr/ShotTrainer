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


@dataclass(slots=True, frozen=True)
class ImageAdjustment:
    """The brightness and contrast the optimiser settled on."""

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
    brightness_steps: tuple[float, ...] = (-20.0, 0.0, 20.0),
    contrast_steps: tuple[float, ...] = (0.8, 1.0, 1.25),
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
    """Search the inner block/offset/blur grid for one image adjustment.

    Stages the work so the Gaussian blur runs once per blur
    kernel instead of once per (block, offset, blur) triple.
    The detector is called with ``blur_kernel=0`` so it skips
    its own blur step against an already-blurred frame. The
    blur kernel that produced the best score is stored on the
    returned settings so the live detector applies the same
    blur later.
    """
    adjusted = _apply_adjustment(grey, brightness, contrast)
    best_score = 0.0
    best_settings: DetectorSettings | None = None
    detector = CircleTargetDetector(base_settings)
    for blur in blurs:
        blurred = cv2.GaussianBlur(adjusted, (blur, blur), 0) if blur >= 3 else adjusted
        for block in block_sizes:
            for offset in offsets:
                for closing in closing_kernels:
                    detector.settings = replace(
                        base_settings,
                        adaptive_block_size=block,
                        adaptive_offset=offset,
                        blur_kernel=0,
                        closing_kernel_px=closing,
                    )
                    detector.reset_lock()
                    detection = detector.detect(blurred)
                    if detection.found and detection.confidence > best_score:
                        best_score = detection.confidence
                        best_settings = replace(detector.settings, blur_kernel=blur)
    return _CellResult(
        settings=best_settings,
        adjustment=ImageAdjustment(brightness=brightness, contrast=contrast),
        score=best_score,
    )


def _apply_adjustment(grey: np.ndarray, brightness: float, contrast: float) -> np.ndarray:
    """Return ``grey`` with the given brightness and contrast applied to a copy."""
    if brightness == 0.0 and contrast == 1.0:
        return grey
    return cv2.convertScaleAbs(grey, alpha=contrast, beta=brightness)
