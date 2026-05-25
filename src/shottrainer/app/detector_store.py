"""Saves the auto-tuned detector settings between runs."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, fields
from pathlib import Path

from shottrainer.tracking.detector import DetectorSettings

from .paths import data_dir
from .settings_validation import matches_setting_type

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
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s", p, exc)
        return None
    if not isinstance(raw, dict):
        log.warning("Detector settings file must contain a JSON object. Using defaults")
        return None
    valid = {f.name for f in fields(DetectorSettings)}
    filtered = {k: v for k, v in raw.items() if k in valid}
    defaults = DetectorSettings()
    for key, value in filtered.items():
        if not matches_setting_type(value, getattr(defaults, key)):
            log.warning("Invalid detector setting %s. Using defaults", key)
            return None
    try:
        settings = DetectorSettings(**filtered)
    except TypeError as exc:
        log.warning("Detector settings file looks invalid: %s", exc)
        return None
    if (
        not 0 < settings.min_radius_px <= settings.max_radius_px
        or settings.blur_kernel < 0
        or (settings.blur_kernel >= 3 and settings.blur_kernel % 2 == 0)
        or settings.adaptive_block_size < 3
        or not 0 <= settings.min_circularity <= 1
        or not 0 < settings.region_fraction <= 1
        or settings.lock_radius_px <= 0
        or settings.lock_boost <= 0
        or settings.lock_release_after_misses <= 0
        or settings.opening_kernel_px < 0
        or settings.closing_kernel_px < 0
        or settings.max_candidates <= 0
        or settings.lock_search_radius_factor <= 0
    ):
        log.warning("Detector settings are out of range. Using defaults")
        return None
    return settings


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
