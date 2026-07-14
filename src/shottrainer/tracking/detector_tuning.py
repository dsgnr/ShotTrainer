"""The auto-optimise button's brain.

A pure function over a single frame. It tries the detector with a
small grid of different settings (and a few brightness / contrast
adjustments) and returns whichever combination scored highest.
Doesn't talk to the camera or keep any state of its own. The
``Auto-optimise`` button calls it when the user wants a quick way
to nudge things back into shape after the lighting changed.

The grid is small enough to walk in a single thread (about a
second on a busy 720p frame), but the outer brightness/contrast
sweep parallelises cleanly across CPUs because each cell is
independent. ``optimise_detector_settings`` picks a process
pool when it has more than one core to play with and falls back
to in-process when it doesn't.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
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
    block_sizes: tuple[int, ...] = (15, 21, 31, 41),
    offsets: tuple[int, ...] = (2, 5, 8, 12),
    blurs: tuple[int, ...] = (3, 5, 7),
    brightness_steps: tuple[float, ...] = (-40.0, -20.0, 0.0, 20.0, 40.0),
    contrast_steps: tuple[float, ...] = (0.8, 1.0, 1.25, 1.5),
    workers: int | None = None,
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

    The brightness/contrast outer loop runs in a process pool so
    each ``(brightness, contrast)`` cell uses its own core. Pass
    ``workers=1`` to keep everything in-process (handy for tests).
    Defaults to ``min(cpu_count, len(brightness)*len(contrast))``.
    """
    if frame is None or frame.size == 0:
        return (None, ImageAdjustment(), 0.0)

    cells = [(b, c) for b in brightness_steps for c in contrast_steps]
    if workers is None:
        workers = min(os.cpu_count() or 1, len(cells))

    if workers <= 1:
        results = [
            _evaluate_cell(b, c, frame, base_settings, block_sizes, offsets, blurs)
            for b, c in cells
        ]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    _evaluate_cell,
                    b,
                    c,
                    frame,
                    base_settings,
                    block_sizes,
                    offsets,
                    blurs,
                )
                for b, c in cells
            ]
            results = [f.result() for f in futures]

    best = max(results, key=lambda r: r.score, default=None)
    if best is None or best.settings is None:
        return (None, ImageAdjustment(), 0.0)
    return (best.settings, best.adjustment, best.score)


def _evaluate_cell(
    brightness: float,
    contrast: float,
    frame: np.ndarray,
    base_settings: DetectorSettings,
    block_sizes: tuple[int, ...],
    offsets: tuple[int, ...],
    blurs: tuple[int, ...],
) -> _CellResult:
    """Search the inner block/offset/blur grid for one image adjustment.

    Module-level so the process pool can pickle it. Returns the
    best detector settings for this cell or a result with
    ``settings=None`` when nothing in this cell found the target.
    """
    adjusted = _apply_adjustment(frame, brightness, contrast)
    best_score = 0.0
    best_settings: DetectorSettings | None = None
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
    return _CellResult(
        settings=best_settings,
        adjustment=ImageAdjustment(brightness=brightness, contrast=contrast),
        score=best_score,
    )


def _apply_adjustment(frame: np.ndarray, brightness: float, contrast: float) -> np.ndarray:
    """Return ``frame`` with the given brightness and contrast applied to a copy."""
    if brightness == 0.0 and contrast == 1.0:
        return frame
    return cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)
