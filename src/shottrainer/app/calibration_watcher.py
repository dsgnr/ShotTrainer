"""Live-reload calibration changes from disk.

Polls the calibration file's mtime on a short timer and emits a signal
when it changes so the controller can reapply it. Polling is safer than
``QFileSystemWatcher`` here: editor save patterns (atomic rename, write
to temp, swap) often mean the watcher loses its target file mid-flight.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from shottrainer.tracking.calibration import LinearCalibration

from .calibration_store import calibration_path, load_calibration

log = logging.getLogger(__name__)


class CalibrationWatcher(QObject):
    """Emits ``changed(calibration_or_None)`` when the file mtime changes."""

    changed = Signal(object)

    def __init__(
        self,
        path: Path | None = None,
        interval_ms: int = 1500,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path or calibration_path()
        self._mtime: float | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        # Initialise the baseline so the first tick doesn't refire just
        # just because the file already exists.
        self._mtime = self._current_mtime()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def force_check(self) -> None:
        self._poll()

    def mark_seen(self) -> None:
        """Bump the baseline so the next external write re-triggers but our
        own write doesn't."""
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
        cal: LinearCalibration | None = (
            load_calibration(self._path) if current is not None else None
        )
        self.changed.emit(cal)
