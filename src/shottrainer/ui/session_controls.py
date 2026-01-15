"""Session control bar with a name field, a start/stop action and a summary."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class SessionControls(QWidget):
    start_requested = Signal(str)
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        layout.addWidget(QLabel("Session"))

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. 50m prone")
        self._name.setMaximumWidth(240)
        layout.addWidget(self._name)

        self._start = QPushButton("Start")
        self._stop = QPushButton("Stop")
        self._stop.setEnabled(False)
        layout.addWidget(self._start)
        layout.addWidget(self._stop)

        self._summary = QLabel("No active session")
        self._summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._summary, 1)

        self._start.clicked.connect(self._on_start)
        self._stop.clicked.connect(self._on_stop)

    def set_active(self, active: bool) -> None:
        self._start.setEnabled(not active)
        self._stop.setEnabled(active)
        self._name.setEnabled(not active)

    def set_summary(self, text: str) -> None:
        self._summary.setText(text)

    def session_name(self) -> str:
        return self._name.text().strip()

    def _on_start(self) -> None:
        self.start_requested.emit(self.session_name())

    def _on_stop(self) -> None:
        self.stop_requested.emit()
