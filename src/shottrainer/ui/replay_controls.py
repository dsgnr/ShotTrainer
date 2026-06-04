"""The replay transport buttons.

Drives a player object (set via ``set_player``) but also works
on its own for UI testing. Fires its own signals on every
action so the main window can keep the target view in sync
without each control needing to know about playback
internals.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QToolTip,
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

        # The transport row is three buttons in a fixed order. Build
        # them from a table so the binding (signal, glyph, tooltip,
        # accessible name) lives in one place rather than spread
        # across three near-identical blocks.
        button_specs: tuple[tuple[str, Signal, str, str], ...] = (
            ("⏮", self.reset_clicked, "Reset to the start of the shot window", "Reset replay"),
            ("▶", self.play_clicked, "Play (Space)", "Play replay"),
            ("⏸", self.pause_clicked, "Pause (Space)", "Pause replay"),
        )
        buttons: list[QPushButton] = []
        for glyph, signal, tooltip, accessible_name in button_specs:
            button = self._make_button(
                glyph, tooltip=tooltip, accessible_name=accessible_name
            )
            button.clicked.connect(signal)
            buttons.append(button)
            layout.addWidget(button)
        self._reset, self._play, self._pause = buttons

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.setToolTip("Scrub through the shot window")
        self._slider.setAccessibleName("Replay scrubber")
        layout.addWidget(self._slider, 1)

        self._time_label = QLabel("--:--")
        self._time_label.setFixedWidth(60)
        layout.addWidget(self._time_label)

        # Total duration of the loaded replay window in
        # milliseconds. Used to show the scrubber tooltip in
        # human-readable seconds while the user drags. ``None``
        # while no shot is loaded.
        self._window_duration_ms: int | None = None

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

    def set_window_duration_ms(self, duration_ms: int | None) -> None:
        """Tell the controls how long the loaded replay window is.

        Used to render the time label and the scrubber tooltip
        in seconds. Pass ``None`` when no shot is loaded, which
        also resets the time label to its placeholder.
        """
        self._window_duration_ms = duration_ms
        if duration_ms is None:
            self._time_label.setText("--:--")
        else:
            self._refresh_time_label(self._slider.value() / 1000.0)

    def set_progress(self, fraction: float) -> None:
        v = max(0, min(1000, round(fraction * 1000)))
        self._slider.blockSignals(True)
        self._slider.setValue(v)
        self._slider.blockSignals(False)
        self._refresh_time_label(fraction)

    def set_time_label(self, text: str) -> None:
        """Override the time label with a custom string.

        ``set_progress`` updates the label automatically once a
        window duration has been set, so most callers don't need
        this. Useful when something other than the slider drives
        the readout (a paused state hint, for example).
        """
        self._time_label.setText(text)

    def _refresh_time_label(self, fraction: float) -> None:
        """Format the label as ``MM:SS.S of MM:SS.S``."""
        duration = self._window_duration_ms
        if duration is None:
            return
        offset_ms = round(fraction * duration)
        self._time_label.setText(
            f"{_format_seconds(offset_ms)} / {_format_seconds(duration)}"
        )

    def _on_slider_moved(self, value: int) -> None:
        fraction = value / 1000.0
        self.scrubbed.emit(fraction)
        self._refresh_time_label(fraction)
        # Show a tooltip near the cursor while dragging so the
        # user sees where they're scrubbing to without having to
        # glance at the time label below.
        duration = self._window_duration_ms
        if duration is None:
            return
        offset_ms = round(fraction * duration)
        text = f"{offset_ms / 1000:.2f}\u202fs of {duration / 1000:.2f}\u202fs"
        QToolTip.showText(QCursor.pos(), text, self._slider)


def _format_seconds(milliseconds: int) -> str:
    """Render ``milliseconds`` as ``M:SS.t`` (one decimal of a second)."""
    if milliseconds < 0:
        milliseconds = 0
    total_tenths = round(milliseconds / 100)
    minutes, rest = divmod(total_tenths, 600)
    seconds, tenths = divmod(rest, 10)
    return f"{minutes}:{seconds:02d}.{tenths}"
