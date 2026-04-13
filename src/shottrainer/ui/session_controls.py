"""Session control panel.

Holds a compact stack of widgets. A session name field, a primary
action that swaps between Start and Stop, a secondary clear button,
and a small summary line. Designed to fit a narrow side column
without truncating.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SessionControls(QWidget):
    start_requested = Signal(str)
    stop_requested = Signal()
    clear_shots_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Session name")
        layout.addWidget(self._name)

        # Primary action: one button that toggles its own meaning.
        self._primary = QPushButton("Start session")
        self._primary.setObjectName("primaryButton")
        self._primary.clicked.connect(self._on_primary)
        layout.addWidget(self._primary)

        secondary_row = QHBoxLayout()
        secondary_row.setContentsMargins(0, 0, 0, 0)
        secondary_row.setSpacing(8)
        self._clear = QPushButton("Clear shots")
        self._clear.clicked.connect(self.clear_shots_requested)
        secondary_row.addWidget(self._clear)
        layout.addLayout(secondary_row)

        self._summary = QLabel("Not recording")
        self._summary.setObjectName("sessionSummary")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._active = False

    def set_active(self, active: bool) -> None:
        self._active = active
        self._name.setEnabled(not active)
        self._clear.setEnabled(not active)
        if active:
            self._primary.setText("Stop session")
            self._primary.setProperty("variant", "stop")
        else:
            self._primary.setText("Start session")
            self._primary.setProperty("variant", "")
        # Re-polish so the [variant] selector picks up the change.
        self._primary.style().unpolish(self._primary)
        self._primary.style().polish(self._primary)

    def set_summary(self, text: str) -> None:
        self._summary.setText(text)

    def session_name(self) -> str:
        return self._name.text().strip()

    def _on_primary(self) -> None:
        if self._active:
            self.stop_requested.emit()
        else:
            self.start_requested.emit(self.session_name())
