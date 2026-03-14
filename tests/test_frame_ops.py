from __future__ import annotations

import numpy as np
import pytest

from shottrainer.tracking.frame_ops import flip_frame, rotate_frame, transform_frame


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


def test_flip_noop_when_neither():
    f = _gradient_frame()
    assert flip_frame(f) is f


def test_flip_horizontal_mirrors_columns():
    f = _gradient_frame(h=4, w=6)
    out = flip_frame(f, horizontal=True)
    assert int(out[0, 0, 0]) == int(f[0, -1, 0])


def test_flip_vertical_mirrors_rows():
    f = _gradient_frame(h=4, w=6)
    out = flip_frame(f, vertical=True)
    assert int(out[0, 0, 0]) == int(f[-1, 0, 0])


def test_flip_both_axes():
    f = _gradient_frame(h=4, w=6)
    out = flip_frame(f, horizontal=True, vertical=True)
    assert int(out[0, 0, 0]) == int(f[-1, -1, 0])


def test_transform_noop_passes_through():
    f = _gradient_frame()
    assert transform_frame(f) is f


def test_transform_combines_rotation_and_flip():
    f = _gradient_frame(h=4, w=6)
    via_pipeline = transform_frame(f, rotation_degrees=180, flip_horizontal=True)
    expected = flip_frame(rotate_frame(f, 180), horizontal=True)
    assert (via_pipeline == expected).all()
