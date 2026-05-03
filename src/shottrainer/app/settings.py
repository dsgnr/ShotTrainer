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
    return data_dir() / "settings.json"


def load_preferences(path: Path | None = None) -> Preferences:
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
    try:
        return Preferences(**filtered)
    except TypeError as exc:
        log.warning("Settings file looks invalid: %s. Using defaults", exc)
        return Preferences()


def save_preferences(prefs: Preferences, path: Path | None = None) -> None:
    p = path or settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(prefs), indent=2))
