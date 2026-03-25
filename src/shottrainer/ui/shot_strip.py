"""Horizontal strip of shot chips used in place of a vertical shot list.

Each chip shows the shot number, score (if any) and offset. The chips
scroll horizontally when the count exceeds what fits in view. Selecting
a chip emits the same signal as the older vertical list so the
controller doesn't need to change.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class ShotChipData:
    index: int
    score: str | None
    x_mm: float
    y_mm: float


class ShotStrip(QWidget):
    shot_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(80)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("shotStripScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._strip = QWidget()
        self._strip.setObjectName("shotStrip")
        self._row = QHBoxLayout(self._strip)
        self._row.setContentsMargins(8, 8, 8, 8)
        self._row.setSpacing(8)
        self._row.addStretch(1)
        self._scroll.setWidget(self._strip)
        outer.addWidget(self._scroll)

        self._chips: list[QPushButton] = []
        self._selected: int | None = None

    def set_shots(self, shots) -> None:
        # Remove old chips.
        for chip in self._chips:
            chip.deleteLater()
        self._chips.clear()
        # Reset stretch.
        while self._row.count():
            item = self._row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for shot in shots:
            data = ShotChipData(
                index=shot.index,
                score=getattr(shot, "score", None),
                x_mm=getattr(shot, "x_mm", 0.0),
                y_mm=getattr(shot, "y_mm", 0.0),
            )
            chip = self._make_chip(data)
            self._chips.append(chip)
            self._row.addWidget(chip)
        self._row.addStretch(1)
        if self._selected is not None:
            self.set_selected(self._selected)

    def set_selected(self, index: int | None) -> None:
        self._selected = index
        for i, chip in enumerate(self._chips):
            chip.setProperty("active", i == index)
            chip.style().unpolish(chip)
            chip.style().polish(chip)

    def _make_chip(self, shot: ShotChipData) -> QPushButton:
        chip = QPushButton()
        chip.setObjectName("shotChip")
        chip.setCheckable(False)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.setMinimumWidth(72)
        # Two-line label: number on top, score / offset below.
        score = shot.score or "-"
        offset = f"{shot.x_mm:+.1f}, {shot.y_mm:+.1f}"
        label = "<div style='text-align:center;'>"
        label += f"<span style='font-size:18px; font-weight:600;'>#{shot.index + 1}</span><br/>"
        label += f"<span style='font-size:10px; color:#8a93a4;'>{score}</span><br/>"
        label += f"<span style='font-size:9px; color:#5a6478;'>{offset}</span>"
        label += "</div>"
        inner = QLabel(label)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.setTextFormat(Qt.TextFormat.RichText)
        chip_layout = QVBoxLayout(chip)
        chip_layout.setContentsMargins(8, 4, 8, 4)
        chip_layout.addWidget(inner)
        chip.clicked.connect(lambda _checked=False, idx=shot.index: self.shot_selected.emit(idx))
        return chip
