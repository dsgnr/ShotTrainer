"""Persist the most recent calibration so it survives restarts.

The store handles both flavours of calibration (linear scale and full
homography). It writes a small JSON file and round-trips into the
``Tracker`` calibration objects.

A separate "zero offset" file lives alongside the calibration. It
holds the user's preferred origin shift (set via the Zero on aim
button) so the trace lines up with where the rifle actually points
once they've zeroed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from shottrainer.tracking.calibration import HomographyCalibration, LinearCalibration

from .paths import data_dir

log = logging.getLogger(__name__)


def calibration_path() -> Path:
    return data_dir() / "calibration.json"


def zero_offset_path() -> Path:
    return data_dir() / "zero_offset.json"


def save_calibration(
    cal: LinearCalibration | HomographyCalibration | None,
    path: Path | None = None,
) -> None:
    p = path or calibration_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    if cal is None:
        try:
            p.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Could not remove %s: %s", p, exc)
        return

    payload = _serialise(cal)
    p.write_text(json.dumps(payload, indent=2))


def load_calibration(
    path: Path | None = None,
) -> LinearCalibration | HomographyCalibration | None:
    p = path or calibration_path()
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s", p, exc)
        return None
    return _deserialise(raw)


def serialise_calibration(
    cal: LinearCalibration | HomographyCalibration | None,
) -> dict | None:
    """Return a JSON-friendly dict for a calibration, or ``None`` if absent."""
    if cal is None:
        return None
    return _serialise(cal)


def _serialise(cal: LinearCalibration | HomographyCalibration) -> dict:
    if isinstance(cal, LinearCalibration):
        return {
            "type": "linear",
            "mm_per_pixel": cal.mm_per_pixel,
            "origin_px": list(cal.origin_px),
        }
    return {
        "type": "homography",
        "matrix": cal.matrix.tolist(),
        "image_points": [list(p) for p in cal.image_points],
        "target_points_mm": [list(p) for p in cal.target_points_mm],
    }


def _deserialise(raw: dict) -> LinearCalibration | HomographyCalibration | None:
    kind = raw.get("type")
    if kind == "linear":
        try:
            origin = tuple(raw.get("origin_px", (0.0, 0.0)))
            return LinearCalibration(
                mm_per_pixel=float(raw["mm_per_pixel"]),
                origin_px=(float(origin[0]), float(origin[1])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("Linear calibration was not readable: %s", exc)
            return None
    if kind == "homography":
        try:
            matrix = np.array(raw["matrix"], dtype=np.float64)
            inverse = np.linalg.inv(matrix)
            image_points = tuple(tuple(p) for p in raw.get("image_points", ()))
            target_points = tuple(tuple(p) for p in raw.get("target_points_mm", ()))
            return HomographyCalibration(
                matrix=matrix,
                inverse=inverse,
                image_points=image_points,
                target_points_mm=target_points,
            )
        except (KeyError, ValueError, np.linalg.LinAlgError) as exc:
            log.warning("Homography calibration was not readable: %s", exc)
            return None
    return None


def save_zero_offset(
    offset_mm: tuple[float, float] | None,
    path: Path | None = None,
) -> None:
    p = path or zero_offset_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    if offset_mm is None or offset_mm == (0.0, 0.0):
        try:
            p.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Could not remove %s: %s", p, exc)
        return
    p.write_text(json.dumps({"x_mm": offset_mm[0], "y_mm": offset_mm[1]}, indent=2))


def load_zero_offset(path: Path | None = None) -> tuple[float, float]:
    p = path or zero_offset_path()
    if not p.exists():
        return (0.0, 0.0)
    try:
        raw = json.loads(p.read_text())
        return (float(raw["x_mm"]), float(raw["y_mm"]))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        log.warning("Could not read %s: %s", p, exc)
        return (0.0, 0.0)
