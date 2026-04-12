"""Top-of-window header bar.

Shows the app name, the current session state, total shots and a running
score. Uses big, calm typography so the user can read it at a glance from
shooting distance.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolButton, QWidget


class AppHeader(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("appHeader")
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 10, 24, 10)
        layout.setSpacing(28)

        self._title = QLabel("ShotTrainer")
        self._title.setObjectName("appHeaderTitle")
        layout.addWidget(self._title)

        self._state_dot = QLabel("\u25CF")
        self._state_dot.setObjectName("appHeaderStateDot")
        self._state_label = QLabel("Idle")
        self._state_label.setObjectName("appHeaderStateLabel")
        layout.addSpacing(20)
        layout.addWidget(self._state_dot)
        layout.addWidget(self._state_label)

        layout.addStretch(1)

        self._shots = self._make_metric("Shots", "0")
        self._score = self._make_metric("Score", "-")
        self._best = self._make_metric("Best", "-")
        for w in (self._shots, self._score, self._best):
            layout.addWidget(w)

        layout.addSpacing(10)
        self.settings_button = QToolButton()
        self.settings_button.setText("\u2699")  # gear icon
        self.settings_button.setObjectName("appHeaderSettings")
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.setToolTip("Preferences")
        layout.addWidget(self.settings_button)

        self.set_state("idle")

    def set_state(self, state: str) -> None:
        """state in {idle, recording, replay}."""
        labels = {
            "idle": ("Idle", "#7a8090"),
            "recording": ("Recording", "#e74c3c"),
            "replay": ("Replay", "#2d6cdf"),
            "calibrating": ("Calibrating", "#f39c12"),
        }
        text, colour = labels.get(state, labels["idle"])
        self._state_label.setText(text)
        self._state_dot.setStyleSheet(f"color: {colour}; font-size: 18px;")

    def set_shot_count(self, n: int) -> None:
        self._shots.value.setText(str(n))

    def set_score(self, value: str) -> None:
        self._score.value.setText(value)

    def set_best(self, value: str) -> None:
        self._best.value.setText(value)

    def _make_metric(self, label: str, value: str) -> _HeaderMetric:
        return _HeaderMetric(label, value)


class _HeaderMetric(QWidget):
    """Caption stacked above a large value."""

    def __init__(self, caption: str, initial: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.caption = QLabel(caption)
        self.caption.setObjectName("appHeaderCaption")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.value = QLabel(initial)
        self.value.setObjectName("appHeaderValue")
        self.value.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self.caption)
        layout.addWidget(self.value)
