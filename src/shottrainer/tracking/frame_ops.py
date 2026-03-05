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
