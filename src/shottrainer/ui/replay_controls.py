"""The replay transport buttons.

Drives a player object (set via ``set_player``) but also works
on its own for UI testing. Sends out its own signals on every
action so the main window can keep the target view in sync
without each control needing to know about playback
internals.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)


class ReplayControls(QWidget):
    play_clicked = Signal()
    pause_clicked = Signal()
    reset_clicked = Signal()
    scrubbed = Signal(float)  # 0.0 to 1.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._reset = self._make_button(
            "⏮",
            tooltip="Reset to the start of the shot window",
            accessible_name="Reset replay",
        )
        self._play = self._make_button(
            "▶",
            tooltip="Play (Space)",
            accessible_name="Play replay",
        )
        self._pause = self._make_button(
            "⏸",
            tooltip="Pause (Space)",
            accessible_name="Pause replay",
        )
        for btn in (self._reset, self._play, self._pause):
            layout.addWidget(btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.setToolTip("Scrub through the shot window")
        self._slider.setAccessibleName("Replay scrubber")
        layout.addWidget(self._slider, 1)

        self._time_label = QLabel("--:--")
        self._time_label.setFixedWidth(60)
        layout.addWidget(self._time_label)

        self._play.clicked.connect(self.play_clicked)
        self._pause.clicked.connect(self.pause_clicked)
        self._reset.clicked.connect(self.reset_clicked)
        self._slider.sliderMoved.connect(self._on_slider_moved)

        self.set_enabled(False)

    @staticmethod
    def _make_button(glyph: str, *, tooltip: str, accessible_name: str) -> QPushButton:
        """A small factory for the transport buttons.

        We use a Unicode transport glyph rather than
        ``QStyle.standardIcon`` so the button picks up the dark
        theme's text colour. The tooltip and accessible name
        are set together so screen readers and cursor hovers
        see the same text.
        """
        button = QPushButton(glyph)
        button.setFixedWidth(40)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setAccessibleName(accessible_name)
        font = button.font()
        font.setPointSize(max(font.pointSize(), 14))
        button.setFont(font)
        return button

    def set_enabled(self, enabled: bool) -> None:
        for w in (self._play, self._pause, self._reset, self._slider):
            w.setEnabled(enabled)

    def set_progress(self, fraction: float) -> None:
        v = max(0, min(1000, round(fraction * 1000)))
        self._slider.blockSignals(True)
        self._slider.setValue(v)
        self._slider.blockSignals(False)

    def set_time_label(self, text: str) -> None:
        self._time_label.setText(text)

    def _on_slider_moved(self, value: int) -> None:
        self.scrubbed.emit(value / 1000.0)
