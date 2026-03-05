from __future__ import annotations

import numpy as np
import pytest

from shottrainer.tracking.frame_ops import rotate_frame


def _gradient_frame(h: int = 30, w: int = 40) -> np.ndarray:
    base = np.arange(h * w, dtype=np.uint8).reshape(h, w)
    return np.stack([base, base, base], axis=-1)


def test_zero_returns_input():
    f = _gradient_frame()
    out = rotate_frame(f, 0)
    assert out is f


def test_90_swaps_dimensions():
    f = _gradient_frame(h=30, w=40)
    out = rotate_frame(f, 90)
    assert out.shape == (40, 30, 3)
    # Top-left pixel of the rotation should come from bottom-left of original.
    assert int(out[0, 0, 0]) == int(f[-1, 0, 0])


def test_180_flips_both_axes():
    f = _gradient_frame()
    out = rotate_frame(f, 180)
    assert out.shape == f.shape
    assert int(out[0, 0, 0]) == int(f[-1, -1, 0])


def test_270_swaps_and_flips():
    f = _gradient_frame(h=30, w=40)
    out = rotate_frame(f, 270)
    assert out.shape == (40, 30, 3)
    assert int(out[0, 0, 0]) == int(f[0, -1, 0])


def test_invalid_rotation_raises():
    with pytest.raises(ValueError):
        rotate_frame(_gradient_frame(), 45)
