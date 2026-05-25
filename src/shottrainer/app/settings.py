"""Save and load preferences as a small JSON file."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from .paths import data_dir
from .preferences import Preferences
from .settings_validation import matches_setting_type

log = logging.getLogger(__name__)

# Match the ranges offered by the Preferences dialog.
_RANGES = {
    "camera_brightness": (-100, 100),
    "camera_contrast": (0.5, 2.0),
    "audio_gain": (0.1, 10.0),
    "shot_threshold": (0.01, 1.0),
    "shot_refractory_ms": (50, 5000),
    "pre_shot_ms": (0, 10000),
    "post_shot_ms": (0, 10000),
    "release_window_ms": (50, 2000),
    "shot_diameter_mm": (0.5, 25.0),
    "tracking_region_fraction": (0.1, 1.0),
    "circle_diameter_mm": (5.0, 1000.0),
}


def settings_path() -> Path:
    """The on-disk path for ``settings.json``."""
    return data_dir() / "settings.json"


def load_preferences(path: Path | None = None) -> Preferences:
    """Read saved preferences, falling back to defaults if needed.

    Unknown keys are dropped silently, so adding new fields in a
    later release doesn't break older settings files. Parse
    errors are logged and we return defaults rather than raising.
    """
    p = path or settings_path()
    if not p.exists():
        return Preferences()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s. Using defaults", p, exc)
        return Preferences()

    if not isinstance(raw, dict):
        log.warning("Settings file must contain a JSON object. Using defaults")
        return Preferences()

    valid = {f.name for f in fields(Preferences)}
    unknown = set(raw) - valid
    if unknown:
        log.debug("Ignoring unknown preference keys: %s", sorted(unknown))
    defaults = Preferences()
    filtered: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in valid:
            continue
        if key == "camera_id" and value is None:
            filtered[key] = None
            continue
        valid_value = matches_setting_type(value, getattr(defaults, key))
        if valid_value and key in _RANGES:
            low, high = _RANGES[key]
            valid_value = low <= value <= high
        if valid_value and key == "camera_rotation":
            valid_value = value in (0, 90, 180, 270)
        if valid_value and key == "camera_id":
            valid_value = value >= 0
        if valid_value:
            filtered[key] = value
        else:
            log.warning("Invalid preference %s. Using its default", key)
    return Preferences(**filtered)


def save_preferences(prefs: Preferences, path: Path | None = None) -> None:
    """Write preferences to disk, creating the data directory if needed."""
    p = path or settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(prefs), indent=2))
