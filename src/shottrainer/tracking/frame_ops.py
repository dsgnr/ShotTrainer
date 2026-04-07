"""Small helpers for spinning a frame around or adjusting brightness."""

from __future__ import annotations

import cv2
import numpy as np


def rotate_frame(frame: np.ndarray, degrees: int) -> np.ndarray:
    """Rotate a frame by 0, 90, 180 or 270 degrees clockwise."""
    d = degrees % 360
    if d == 0:
        return frame
    if d == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if d == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if d == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"Unsupported rotation: {degrees}")


def flip_frame(frame: np.ndarray, horizontal: bool = False, vertical: bool = False) -> np.ndarray:
    """Mirror a frame horizontally, vertically, or both.

    When both flips are asked for, OpenCV does it in a single pass
    rather than two.
    """
    if not horizontal and not vertical:
        return frame
    if horizontal and vertical:
        return cv2.flip(frame, -1)
    if horizontal:
        return cv2.flip(frame, 1)
    return cv2.flip(frame, 0)


def adjust_image(
    frame: np.ndarray,
    *,
    brightness: float = 0.0,
    contrast: float = 1.0,
) -> np.ndarray:
    """Apply linear brightness and contrast to a frame.

    ``contrast`` is a multiplier where 1.0 means no change.
    ``brightness`` is an additive offset in 0..255 units where 0.0
    means no change. Pixels are clipped to fit a uint8. When both
    parameters are at their identity values the input is returned
    unchanged so the common case doesn't pay for a copy.
    """
    if contrast == 1.0 and brightness == 0.0:
        return frame
    return cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)


def transform_frame(
    frame: np.ndarray,
    *,
    rotation_degrees: int = 0,
    flip_horizontal: bool = False,
    flip_vertical: bool = False,
    brightness: float = 0.0,
    contrast: float = 1.0,
) -> np.ndarray:
    """Run rotation, flip and image controls in one call.

    The order matters. Rotating after flipping would change what
    "horizontal" means, so rotation runs first and the flip axes
    line up with what the user sees in the preview. Brightness and
    contrast come last so the detector and the preview both see
    the corrected image.
    """
    if rotation_degrees:
        frame = rotate_frame(frame, rotation_degrees)
    if flip_horizontal or flip_vertical:
        frame = flip_frame(frame, horizontal=flip_horizontal, vertical=flip_vertical)
    if contrast != 1.0 or brightness != 0.0:
        frame = adjust_image(frame, brightness=brightness, contrast=contrast)
    return frame
