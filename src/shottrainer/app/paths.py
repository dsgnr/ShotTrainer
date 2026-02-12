"""Where the app keeps its data.

Holds the platform check in one place. Each platform has its
own conventional location. ``%APPDATA%/ShotTrainer`` on
Windows, ``~/Library/Application Support/ShotTrainer`` on
macOS, and ``$XDG_DATA_HOME/shottrainer`` (with a sensible
fallback) on Linux.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ShotTrainer"


def data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(base) / "shottrainer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return data_dir() / "sessions.db"
