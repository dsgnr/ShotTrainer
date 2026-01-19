"""The session browser dialog.

Lists previously recorded sessions, lets the user open one
for replay or delete it. The dialog reads from a
:class:`SessionRepository` that it doesn't own.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shottrainer.sessions.repository import SessionRepository, SessionSummary


class SessionBrowserDialog(QDialog):
    open_session = Signal(int)

    def __init__(self, repository: SessionRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sessions")
        self.resize(560, 420)
        self._repo = repository

        layout = QVBoxLayout(self)

        self._list = QListWidget()
        layout.addWidget(self._list, 1)

        actions = QHBoxLayout()
        self._open = QPushButton("Open")
        self._delete = QPushButton("Delete")
        actions.addWidget(self._open)
        actions.addWidget(self._delete)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        layout.addWidget(buttons)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        self._open.clicked.connect(self._on_open)
        self._delete.clicked.connect(self._on_delete)

        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        for s in self._repo.list_sessions():
            self._list.addItem(_make_item(s))

    def _selected_session_id(self) -> int | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return int(item.data(0x0100))

    def _on_open(self) -> None:
        sid = self._selected_session_id()
        if sid is None:
            return
        self.open_session.emit(sid)
        self.accept()

    def _on_delete(self) -> None:
        sid = self._selected_session_id()
        if sid is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete session",
            "Delete this session and all its trace data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._repo.delete_session(sid)
            self.refresh()


def _make_item(summary: SessionSummary) -> QListWidgetItem:
    started = summary.started_at.strftime("%Y-%m-%d %H:%M")
    label = f"{started}   {summary.name or '(unnamed)'}   ({summary.shot_count} shots)"
    item = QListWidgetItem(label)
    item.setData(0x0100, summary.id)
    return item
