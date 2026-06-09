"""Top-of-window status strip.

The app name, a state pill, and a settings cog. Numbers and
metrics live in the right column where they have room to breathe.
"""

from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolButton, QWidget


class _StateStyle(NamedTuple):
    """Display attributes for one entry in the state pill."""

    text: str
    colour: str


_STATE_STYLES: dict[str, _StateStyle] = {
    "idle": _StateStyle("Idle", "#7a8090"),
    "recording": _StateStyle("Recording", "#e74c3c"),
    "replay": _StateStyle("Replay", "#2d6cdf"),
}


class StatePill(QLabel):
    """Small coloured pill showing the current session state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise with the default idle state.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("statePill")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(110)
        self.set_state("idle")

    def set_state(self, state: str) -> None:
        """Update the pill's text and colour for the given state."""
        style = _STATE_STYLES.get(state, _STATE_STYLES["idle"])
        self.setText(style.text)
        self.setStyleSheet(
            f"QLabel#statePill {{ color: {style.colour}; border-color: {style.colour}; }}"
        )


class AppHeader(QWidget):
    """Top-of-window status strip with app name, state pill, and settings cog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the header layout.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("appHeader")
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 16, 8)
        layout.setSpacing(16)

        self._title = QLabel("ShotTrainer")
        self._title.setObjectName("appHeaderTitle")
        layout.addWidget(self._title)

        layout.addSpacing(8)
        self._state = StatePill()
        layout.addWidget(self._state)

        layout.addStretch(1)

        self._status_hint = QLabel("Acquiring target...")
        self._status_hint.setObjectName("appHeaderHint")
        self._status_hint.setToolTip(
            "Live mm-per-pixel reading. Lower means the camera is "
            "further from the target. The trace is correct in mm "
            "as soon as this number stabilises."
        )
        layout.addWidget(self._status_hint)

        self.settings_button = QToolButton()
        self.settings_button.setText("\u2699")
        self.settings_button.setObjectName("appHeaderSettings")
        self.settings_button.setFixedSize(32, 32)
        self.settings_button.setToolTip("Preferences")
        layout.addWidget(self.settings_button)

    def set_state(self, state: str) -> None:
        """Delegate to the `StatePill` to update the session state display."""
        self._state.set_state(state)

    def set_status_text(self, text: str) -> None:
        """Update the secondary hint shown next to the state pill.

        Used for the live "Tracking N mm circle - X.YZ mm/px" readout
        the controller refreshes a few times per second.
        """
        self._status_hint.setText(text)
