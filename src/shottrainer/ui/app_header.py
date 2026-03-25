"""Top-of-window status strip.

The app name, a state pill, and a settings cog. Numbers and
metrics live in the right column where they have room to breathe.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolButton, QWidget

_STATE_COLOURS: dict[str, tuple[str, str]] = {
    "idle": ("Idle", "#7a8090"),
    "recording": ("Recording", "#e74c3c"),
    "replay": ("Replay", "#2d6cdf"),
    "calibrating": ("Calibrating", "#f39c12"),
}


class StatePill(QLabel):
    """Small coloured pill showing the current session state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statePill")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(110)
        self.set_state("idle")

    def set_state(self, state: str) -> None:
        text, colour = _STATE_COLOURS.get(state, _STATE_COLOURS["idle"])
        self.setText(text)
        self.setStyleSheet(
            "QLabel#statePill {"
            f"  color: {colour};"
            f"  border: 1px solid {colour};"
            "  border-radius: 12px;"
            "  padding: 4px 12px;"
            "  font-size: 11px;"
            "  letter-spacing: 1.5px;"
            "  text-transform: uppercase;"
            "}"
        )


class AppHeader(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
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

        self._calibration = QLabel("Uncalibrated")
        self._calibration.setObjectName("appHeaderHint")
        layout.addWidget(self._calibration)

        self.settings_button = QToolButton()
        self.settings_button.setText("\u2699")
        self.settings_button.setObjectName("appHeaderSettings")
        self.settings_button.setFixedSize(32, 32)
        self.settings_button.setToolTip("Preferences")
        layout.addWidget(self.settings_button)

    def set_state(self, state: str) -> None:
        self._state.set_state(state)

    def set_calibration_text(self, text: str) -> None:
        self._calibration.setText(text)

    # Legacy API kept so the controller can ignore the redesign:
    def set_shot_count(self, _n: int) -> None:
        pass

    def set_score(self, _value: str) -> None:
        pass

    def set_best(self, _value: str) -> None:
        pass
