"""Reloads preferences from disk while the app is running.

Mirrors :mod:`calibration_watcher`: polls ``settings.json`` for
modification time changes and emits a signal when it sees one. Useful
when an external editor or another tool rewrites preferences while the
app is running.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from shottrainer.ui.preferences_dialog import Preferences

from .settings import load_preferences, settings_path

log = logging.getLogger(__name__)


class SettingsWatcher(QObject):
    """Fires ``changed(Preferences)`` when ``settings.json`` is updated."""

    changed = Signal(object)

    def __init__(
        self,
        path: Path | None = None,
        interval_ms: int = 1500,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path or settings_path()
        self._mtime: float | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        # Take an initial mtime so the first tick doesn't refire
        # just because the file already exists.
        self._mtime = self._current_mtime()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def force_check(self) -> None:
        self._poll()

    def mark_seen(self) -> None:
        """Reset the baseline so an external write fires but our own doesn't."""
        self._mtime = self._current_mtime()

    def _current_mtime(self) -> float | None:
        try:
            return self._path.stat().st_mtime if self._path.exists() else None
        except OSError as exc:
            log.debug("Could not stat %s: %s", self._path, exc)
            return None

    def _poll(self) -> None:
        current = self._current_mtime()
        if current == self._mtime:
            return
        self._mtime = current
        if current is None:
            self.changed.emit(Preferences())
            return
        try:
            prefs = load_preferences(self._path)
        except Exception as exc:  # pragma: no cover - load_preferences already swallows IO errors
            log.warning("Could not reload preferences: %s", exc)
            return
        self.changed.emit(prefs)
