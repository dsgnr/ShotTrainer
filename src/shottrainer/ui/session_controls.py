"""Session control panel.

Holds a compact stack of widgets. A session name field, a category
selector, a primary action that swaps between Start and Stop, a
secondary clear button, and a small summary line. Designed to fit a
narrow side column without truncating.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from shottrainer.sessions.models import DEFAULT_SESSION_CATEGORY, SESSION_CATEGORIES


class SessionControls(QWidget):
    """Session control panel with start/stop, name field, and clear button."""

    start_requested = Signal(str)
    stop_requested = Signal()
    clear_shots_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the session controls layout.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Session name")
        layout.addWidget(self._name)

        # Category picker. The order matches SESSION_CATEGORIES so the
        # default ("practice") sits at the top of the list. Each item
        # carries the underlying string in its userData so the
        # display label can be reworded without touching the
        # database side.
        self._category = QComboBox()
        for value in SESSION_CATEGORIES:
            self._category.addItem(value.capitalize(), value)
        self._category.setCurrentIndex(SESSION_CATEGORIES.index(DEFAULT_SESSION_CATEGORY))
        self._category.setToolTip("Tag this session as practice, sighters, or a match.")
        layout.addWidget(self._category)

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
        """Toggle between the recording and idle UI state.

        Args:
            active: True when a session is being recorded.
        """
        self._active = active
        self._name.setEnabled(not active)
        self._category.setEnabled(not active)
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
        """Update the session summary label.

        Args:
            text: Summary text (e.g. shot count and elapsed time).
        """
        self._summary.setText(text)

    def session_name(self) -> str:
        """Return the current text in the session name field, stripped."""
        return self._name.text().strip()

    def session_category(self) -> str:
        """Return the currently selected category string."""
        value = self._category.currentData()
        if isinstance(value, str):
            return value
        return DEFAULT_SESSION_CATEGORY

    def primary_action(self) -> QPushButton:
        """Return the primary Start/Stop button.

        Exposed for keyboard shortcuts and tests. UI consumers should
        prefer ``start_requested`` / ``stop_requested`` signals.
        """
        return self._primary

    def clear_button(self) -> QPushButton:
        """Return the secondary 'Clear shots' button."""
        return self._clear

    def _on_primary(self) -> None:
        """Emit the appropriate signal based on active state."""
        if self._active:
            self.stop_requested.emit()
        else:
            self.start_requested.emit(self.session_name())
