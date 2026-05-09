"""Compact live audio level meter.

Driven by the same audio listener that feeds the shot detector.
Shows a horizontal bar with a peak hold, so brief spikes stay
visible long enough to read.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

# Level thresholds for the meter bar's three-band colour ramp.
# Below the first threshold the bar is green ("comfortably below
# clipping"). Above the last it's red ("close to clipping"). In
# between it's amber. Stored as a small table so adding a band is a
# one-line change.
_LEVEL_BANDS: tuple[tuple[float, str], ...] = (
    (0.7, "#27ae60"),
    (0.9, "#f39c12"),
    (1.0, "#e74c3c"),
)


def _colour_for_level(level: float) -> QColor:
    for threshold, hex_colour in _LEVEL_BANDS:
        if level < threshold:
            return QColor(hex_colour)
    return QColor(_LEVEL_BANDS[-1][1])


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
            p.fillRect(
                rect.x(),
                rect.y(),
                bar_w,
                rect.height(),
                _colour_for_level(self._level),
            )

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
