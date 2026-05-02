"""Compact live audio level meter.

Driven by the same audio listener that feeds the shot detector.
Shows a horizontal bar with a peak hold, so brief spikes stay
visible long enough to read.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget


class AudioMeter(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._level = 0.0
        self._peak = 0.0
        self._threshold = 0.0

        self._decay = QTimer(self)
        self._decay.timeout.connect(self._tick)
        self._decay.start(50)

    def set_level(self, level: float) -> None:
        v = max(0.0, min(1.0, float(level)))
        self._level = v
        if v > self._peak:
            self._peak = v
        self.update()

    def set_threshold(self, threshold: float) -> None:
        self._threshold = max(0.0, min(1.0, float(threshold)))
        self.update()

    def _tick(self) -> None:
        self._level = max(0.0, self._level * 0.85)
        self._peak = max(0.0, self._peak * 0.97)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        p = QPainter(self)
        rect = self.rect()
        # Background.
        p.fillRect(rect, QColor("#15171b"))

        # Fill the bar in segments coloured by level so it reads as a meter.
        bar_w = int(rect.width() * self._level)
        if bar_w > 0:
            colour = QColor("#27ae60") if self._level < 0.7 else (
                QColor("#f39c12") if self._level < 0.9 else QColor("#e74c3c")
            )
            p.fillRect(rect.x(), rect.y(), bar_w, rect.height(), colour)

        # Peak indicator: 2 px line at the highest level seen recently.
        if self._peak > 0:
            x = rect.x() + int(rect.width() * self._peak)
            p.fillRect(x - 1, rect.y(), 2, rect.height(), QColor("#ecf0f1"))

        # Threshold marker.
        if self._threshold > 0:
            x = rect.x() + int(rect.width() * self._threshold)
            p.fillRect(x - 1, rect.y(), 2, rect.height(), QColor("#2d6cdf"))

        p.setPen(QColor("#2c303a"))
        p.drawRect(rect.adjusted(0, 0, -1, -1))
