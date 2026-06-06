"""Saves the auto-tuned detector settings between runs.

Kept separate from preferences because these settings come out of
the auto-optimiser, not the user. The file can be deleted without
losing anything. The optimiser picks new values the next time the
user clicks the button.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, fields
from pathlib import Path

from shottrainer.tracking.detector import DetectorSettings

from .paths import data_dir

log = logging.getLogger(__name__)


def detector_settings_path() -> Path:
    """The on-disk path for ``detector_settings.json``."""
    return data_dir() / "detector_settings.json"


def load_detector_settings(path: Path | None = None) -> DetectorSettings | None:
    """Return saved detector settings, or ``None`` if there are none.

    ``None`` lets the caller fall back to whichever defaults make
    sense for the current preferences (typically a fresh
    :class:`DetectorSettings` parameterised by the chosen
    tracking-region fraction).
    """
    p = path or detector_settings_path()
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s", p, exc)
        return None
    valid = {f.name for f in fields(DetectorSettings)}
    filtered = {k: v for k, v in raw.items() if k in valid}
    try:
        return DetectorSettings(**filtered)
    except TypeError as exc:
        log.warning("Detector settings file looks invalid: %s", exc)
        return None


def save_detector_settings(settings: DetectorSettings, path: Path | None = None) -> None:
    """Write the tuned detector settings to disk."""
    p = path or detector_settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(settings), indent=2))


def clear_detector_settings(path: Path | None = None) -> None:
    """Delete the detector settings file. No error if it isn't there."""
    p = path or detector_settings_path()
    try:
        p.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("Could not remove %s: %s", p, exc)
