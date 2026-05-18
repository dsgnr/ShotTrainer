"""Reloads preferences from disk while the app is running.

Watches ``settings.json`` for changes to its modification time
and fires a signal when it spots one. Handy when an external
editor or another tool rewrites the file while the app is open.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from shottrainer.app.preferences import Preferences

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
        """Begin polling and remember the file's current mtime.

        Seeding the baseline means the first tick after start
        doesn't fire ``changed`` just because the file already
        exists. Only edits made *after* ``start`` trigger a
        reload.
        """
        # Take an initial mtime so the first tick doesn't refire
        # just because the file already exists.
        self._mtime = self._current_mtime()
        self._timer.start()

    def stop(self) -> None:
        """Stop the poll timer. Safe to call more than once."""
        self._timer.stop()

    def force_check(self) -> None:
        """Run a single poll cycle synchronously. Used by tests."""
        self._poll()

    def mark_seen(self) -> None:
        """Reset the baseline so an external write fires but our own doesn't."""
        self._mtime = self._current_mtime()

    def _current_mtime(self) -> float | None:
        """The file's current mtime, or ``None`` if it's missing or unreadable."""
        try:
            return self._path.stat().st_mtime if self._path.exists() else None
        except OSError as exc:
            log.debug("Could not stat %s: %s", self._path, exc)
            return None

    def _poll(self) -> None:
        """Compare the current mtime against the baseline and fire on change.

        If the file has vanished we emit a default
        :class:`Preferences` so the controller falls back to
        defaults rather than holding stale values.
        """
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
