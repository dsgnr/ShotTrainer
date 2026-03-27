"""Search a small grid of detector settings for the best confidence.

Pure function over a single frame: it doesn't talk to the camera, it
doesn't keep state. Useful for the "Auto-optimise" button so the user
gets a one-click way to nudge the detector when lighting changes.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from .detector import CircleTargetDetector, DetectorSettings


def optimise_detector_settings(
    frame: np.ndarray,
    base_settings: DetectorSettings,
    *,
    block_sizes: tuple[int, ...] = (15, 21, 31, 41),
    offsets: tuple[int, ...] = (2, 5, 8, 12),
    blurs: tuple[int, ...] = (3, 5, 7),
) -> tuple[DetectorSettings | None, float]:
    """Return (settings, confidence) of the best-scoring combination.

    Walks a small grid of adaptive-threshold parameters and Gaussian blur
    kernels and runs the detector against ``frame`` for each one.
    Returns ``(None, 0.0)`` if nothing scored above zero, which usually
    means the target isn't visible in the frame at all.
    """
    if frame is None or frame.size == 0:
        return (None, 0.0)

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
                detection = detector.detect(frame)
                if detection.found and detection.confidence > best_score:
                    best_score = detection.confidence
                    best_settings = candidate
    return (best_settings, best_score)
