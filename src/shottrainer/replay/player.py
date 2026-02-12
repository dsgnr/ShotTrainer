"""Plays a saved trace back at the original speed (or scrubbed)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QObject, QTimer, Signal

from shottrainer.tracking.models import TrackingSample


class TracePlayer(QObject):
    point = Signal(float, float)  # x_mm, y_mm
    progress = Signal(float)       # 0.0..1.0
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._samples: list[TrackingSample] = []
        self._index: int = 0
        self._playing: bool = False
        self._speed: float = 1.0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._step)

    def load(self, samples: Sequence[TrackingSample]) -> None:
        self.stop()
        self._samples = [s for s in samples if s.x_mm is not None and s.y_mm is not None]
        self._index = 0
        self._emit_current()
        self.progress.emit(0.0)

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.1, speed)

    def play(self) -> None:
        if not self._samples or self._playing:
            return
        if self._index >= len(self._samples) - 1:
            self._index = 0
        self._playing = True
        self._schedule_next()

    def pause(self) -> None:
        self._playing = False
        self._timer.stop()

    def stop(self) -> None:
        self.pause()
        self._index = 0
        if self._samples:
            self._emit_current()
        self.progress.emit(0.0)

    def seek_fraction(self, f: float) -> None:
        if not self._samples:
            return
        f = max(0.0, min(1.0, f))
        self._index = int(round(f * (len(self._samples) - 1)))
        self._emit_current()
        self.progress.emit(self._index / max(1, len(self._samples) - 1))

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def length(self) -> int:
        return len(self._samples)

    def _schedule_next(self) -> None:
        if self._index >= len(self._samples) - 1:
            self._playing = False
            self.finished.emit()
            return
        cur = self._samples[self._index]
        nxt = self._samples[self._index + 1]
        delay_ms = max(1, int(round((nxt.timestamp - cur.timestamp) * 1000.0 / self._speed)))
        self._timer.start(delay_ms)

    def _step(self) -> None:
        if not self._playing:
            return
        self._index += 1
        self._emit_current()
        self.progress.emit(self._index / max(1, len(self._samples) - 1))
        self._schedule_next()

    def _emit_current(self) -> None:
        if not self._samples:
            return
        s = self._samples[self._index]
        if s.x_mm is not None and s.y_mm is not None:
            self.point.emit(float(s.x_mm), float(s.y_mm))
