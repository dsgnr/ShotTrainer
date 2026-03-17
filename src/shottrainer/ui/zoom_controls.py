"""Zoom slider for the target view."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget


class ZoomControls(QWidget):
    extent_changed = Signal(float)  # new extent in mm

    def __init__(
        self,
        min_extent_mm: float = 5.0,
        max_extent_mm: float = 500.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._min = min_extent_mm
        self._max = max_extent_mm

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 4)

        layout.addWidget(QLabel("Zoom"))

        self._out = QPushButton("-")
        self._out.setFixedWidth(28)
        layout.addWidget(self._out)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        layout.addWidget(self._slider, 1)

        self._in = QPushButton("+")
        self._in.setFixedWidth(28)
        layout.addWidget(self._in)

        self._readout = QLabel("- mm")
        self._readout.setFixedWidth(70)
        layout.addWidget(self._readout)

        self._slider.valueChanged.connect(self._on_slider)
        self._in.clicked.connect(lambda: self._slider.setValue(self._slider.value() - 50))
        self._out.clicked.connect(lambda: self._slider.setValue(self._slider.value() + 50))

    def set_extent(self, extent_mm: float) -> None:
        clamped = min(self._max, max(self._min, float(extent_mm)))
        ratio = math.log(clamped / self._min) / math.log(self._max / self._min)
        value = round(ratio * 1000)
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        self._readout.setText(f"{clamped:.0f} mm")

    def _on_slider(self, value: int) -> None:
        ratio = value / 1000.0
        extent = self._min * ((self._max / self._min) ** ratio)
        self._readout.setText(f"{extent:.0f} mm")
        self.extent_changed.emit(extent)
