"""Save and load preferences as a small JSON file."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, fields
from pathlib import Path

from .paths import data_dir
from .preferences import Preferences

log = logging.getLogger(__name__)


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
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s. Using defaults", p, exc)
        return Preferences()

    valid = {f.name for f in fields(Preferences)}
    unknown = set(raw) - valid
    if unknown:
        log.debug("Ignoring unknown preference keys: %s", sorted(unknown))
    filtered = {k: v for k, v in raw.items() if k in valid}
    # ``camera_brightness`` and ``camera_contrast`` used to be
    # ``float | None`` in a 0..1 range. They're plain floats now,
    # with different defaults. Drop a stale ``None`` so the
    # dataclass falls back to its default instead of raising on
    # the wrong type.
    for key in ("camera_brightness", "camera_contrast"):
        if filtered.get(key) is None:
            filtered.pop(key, None)
    try:
        return Preferences(**filtered)
    except TypeError as exc:
        log.warning("Settings file looks invalid: %s. Using defaults", exc)
        return Preferences()


def save_preferences(prefs: Preferences, path: Path | None = None) -> None:
    """Write preferences to disk, creating the data directory if needed."""
    p = path or settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(prefs), indent=2))
