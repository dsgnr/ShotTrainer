"""The session browser dialog.

Lists previously recorded sessions, lets the user open one
for replay or delete it. The dialog reads from a
:class:`SessionRepository` that it doesn't own.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from shottrainer.services.exporter import export_session_csv
from shottrainer.sessions.repository import SessionRepository, SessionSummary


class SessionBrowserDialog(QDialog):
    open_session = Signal(int)

    def __init__(self, repository: SessionRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sessions")
        self.resize(560, 420)
        self._repo = repository

        layout = QVBoxLayout(self)

        # Either the list or the empty-state placeholder is shown
        # at any one time. Keeping them in a stacked widget means
        # ``refresh`` only flips the visible page rather than
        # rebuilding the layout.
        self._stack = QStackedWidget()
        self._list = QListWidget()
        self._empty = QLabel(
            "No saved sessions yet.\nStart one with the green button on "
            "the main window or with Ctrl+S."
        )
        self._empty.setObjectName("sessionListEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._stack.addWidget(self._list)
        self._stack.addWidget(self._empty)
        layout.addWidget(self._stack, 1)

        actions = QHBoxLayout()
        self._open = QPushButton("Open")
        self._delete = QPushButton("Delete")
        self._export = QPushButton("Export CSV...")
        actions.addWidget(self._open)
        actions.addWidget(self._delete)
        actions.addWidget(self._export)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        layout.addWidget(buttons)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        self._open.clicked.connect(self._on_open)
        self._delete.clicked.connect(self._on_delete)
        self._export.clicked.connect(self._on_export)

        # Open / Delete / Export only make sense with a row
        # selected. Bind their enabled state to the list's
        # selection so the dialog isn't offering buttons that
        # would do nothing.
        self._list.itemDoubleClicked.connect(lambda _item: self._on_open())
        self._list.currentItemChanged.connect(lambda *_: self._refresh_action_buttons())

        self.refresh()

    def refresh(self) -> None:
        """Re-read the session list from the repository and rebuild the rows."""
        self._list.clear()
        sessions = self._repo.list_sessions()
        for s in sessions:
            self._list.addItem(_make_item(s))
        self._stack.setCurrentWidget(self._list if sessions else self._empty)
        self._refresh_action_buttons()

    def _refresh_action_buttons(self) -> None:
        """Enable the action buttons only when a row is selected."""
        has_selection = self._list.currentItem() is not None
        self._open.setEnabled(has_selection)
        self._delete.setEnabled(has_selection)
        self._export.setEnabled(has_selection)

    def _selected_session_id(self) -> int | None:
        """Database id of the currently selected row, or ``None``."""
        item = self._list.currentItem()
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def _on_open(self) -> None:
        """Fire ``open_session`` for the selected row and close the dialog."""
        sid = self._selected_session_id()
        if sid is None:
            return
        self.open_session.emit(sid)
        self.accept()

    def _on_delete(self) -> None:
        """Confirm with the user, then cascade-delete the selected session."""
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

    def _on_export(self) -> None:
        """Ask the user for a folder and write the session's CSVs into it."""
        sid = self._selected_session_id()
        if sid is None:
            return
        target = QFileDialog.getExistingDirectory(self, "Choose export folder")
        if not target:
            return
        from pathlib import Path

        files = export_session_csv(self._repo, sid, Path(target))
        QMessageBox.information(
            self,
            "Export complete",
            f"Wrote {len(files)} files to {target}",
        )


def _make_item(summary: SessionSummary) -> QListWidgetItem:
    """Build a list item for one session, with the id stored as user data."""
    started = summary.started_at.strftime("%Y-%m-%d %H:%M")
    name = summary.name or "(unnamed)"
    duration = _format_duration(summary)
    score = (
        f"   {summary.total_score:g} pts"
        if summary.shot_count and summary.total_score > 0
        else ""
    )
    label = (
        f"{started}   {name}   ({summary.shot_count} shots, {duration})"
        f"{score}"
    )
    item = QListWidgetItem(label)
    item.setData(Qt.ItemDataRole.UserRole, summary.id)
    return item


def _format_duration(summary: SessionSummary) -> str:
    """Return the session length as ``"Xm Ys"`` or ``"in progress"``."""
    if summary.ended_at is None:
        return "in progress"
    delta = summary.ended_at - summary.started_at
    seconds = max(0, int(delta.total_seconds()))
    minutes, seconds = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"
