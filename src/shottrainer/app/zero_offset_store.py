"""Saves the user's zero-on-aim offset across runs.

The trace's origin is normally the centre of the live circle.
When the user clicks *Zero on aim* the origin shifts by
``(x_mm, y_mm)`` so the trace reports distance from wherever
they were aiming at the time. That offset is the only piece of
persistent tracking state the app keeps. The rest is re-derived
from each frame's detection.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .paths import data_dir

log = logging.getLogger(__name__)


def zero_offset_path() -> Path:
    return data_dir() / "zero_offset.json"


def save_zero_offset(
    offset_mm: tuple[float, float] | None,
    path: Path | None = None,
) -> None:
    """Save ``offset_mm`` to disk. ``None`` or ``(0, 0)`` removes the file."""
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
    """Return the saved offset, or ``(0, 0)`` when there isn't one."""
    p = path or zero_offset_path()
    if not p.exists():
        return (0.0, 0.0)
    try:
        raw = json.loads(p.read_text())
        return (float(raw["x_mm"]), float(raw["y_mm"]))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        log.warning("Could not read %s: %s", p, exc)
        return (0.0, 0.0)
