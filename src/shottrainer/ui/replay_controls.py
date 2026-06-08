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
    QSizePolicy,
    QSlider,
    QToolTip,
    QWidget,
)


class ReplayControls(QWidget):
    """Replay transport panel with play/pause, reset, scrubber, and time label."""

    play_clicked = Signal()
    pause_clicked = Signal()
    reset_clicked = Signal()
    scrubbed = Signal(float)  # 0.0 to 1.0

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the transport controls in a disabled state.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        # ``Preferred`` width so the row's stretch element pushes
        # the controls toward the right rather than blowing the
        # transport buttons out across the full width.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # defaults
        self._default_stamp = "0:00.0 / 0:00.0"

        # The transport row is a reset button and a single
        # play/pause button that swaps glyph based on whether
        # the player is currently running. ``set_playing``
        # keeps the button in sync.
        self._reset = self._make_button(
            "⏮",
            tooltip="Reset to the start of the shot window",
            accessible_name="Reset replay",
        )
        self._reset.clicked.connect(self.reset_clicked)
        layout.addWidget(self._reset)

        self._play_pause = self._make_button(
            "▶", tooltip="Play (Space)", accessible_name="Play replay"
        )
        self._play_pause.clicked.connect(self._on_play_pause_clicked)
        self._is_playing = False
        layout.addWidget(self._play_pause)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.setFixedWidth(150)
        self._slider.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Stop the slider widget filling its content rectangle with the
        # palette background.
        self._slider.setAutoFillBackground(False)
        self._slider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._slider.setToolTip("Scrub through the shot window")
        self._slider.setAccessibleName("Replay scrubber")
        layout.addWidget(self._slider)

        self._time_label = QLabel(self._default_stamp)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        # Reserve room for the running readout so the cluster
        # doesn't jump as the label grows from the placeholder.
        self._time_label.setMinimumWidth(
            self._time_label.fontMetrics().horizontalAdvance(self._default_stamp) + 12
        )
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
        """Enable or disable all transport controls.

        Args:
            enabled: Whether the controls should be interactive.
        """
        for w in (self._play_pause, self._reset, self._slider, self._time_label):
            w.setEnabled(enabled)

    def set_window_duration_ms(self, duration_ms: int | None) -> None:
        """Tell the controls how long the loaded replay window is.

        Used to render the time label and the scrubber tooltip
        in seconds. Pass ``None`` when no shot is loaded, which
        also resets the time label to its placeholder.
        """
        self._window_duration_ms = duration_ms
        if duration_ms is None:
            self._time_label.setText(self._default_stamp)
        else:
            self._refresh_time_label(self._slider.value() / 1000.0)

    def set_progress(self, fraction: float) -> None:
        """Move the scrubber to the given position without emitting signals.

        Args:
            fraction: Position between 0.0 and 1.0.
        """
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
        self._time_label.setText(f"{_format_seconds(offset_ms)} / {_format_seconds(duration)}")

    def set_playing(self, playing: bool) -> None:
        """Tell the controls whether the player is currently running.

        Updates the play/pause button's glyph and tooltip so the
        user sees the state at a glance. The controller calls
        this on every progress tick.
        """
        if playing == self._is_playing:
            return
        self._is_playing = playing
        if playing:
            self._play_pause.setText("⏸")
            self._play_pause.setToolTip("Pause (Space)")
            self._play_pause.setAccessibleName("Pause replay")
        else:
            self._play_pause.setText("▶")
            self._play_pause.setToolTip("Play (Space)")
            self._play_pause.setAccessibleName("Play replay")

    def toggle_play_pause(self) -> None:
        """Trigger play or pause depending on the current state.

        Used by the Space shortcut so one key drives both
        directions of the toggle.
        """
        self._on_play_pause_clicked()

    def _on_play_pause_clicked(self) -> None:
        """Emit play or pause depending on current state."""
        if self._is_playing:
            self.pause_clicked.emit()
        else:
            self.play_clicked.emit()

    def _on_slider_moved(self, value: int) -> None:
        """Handle manual scrubbing: emit fraction and show tooltip."""
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
