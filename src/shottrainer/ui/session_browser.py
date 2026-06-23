"""The session browser dialog.

Lists previously recorded sessions, lets the user open one
for replay or delete it. The dialog reads from a
:class:`SessionRepository` that it doesn't own.

The list is loaded after the dialog has had a chance to render so
the window appears immediately even when the database holds many
sessions. While the load is running a small "Loading..."
placeholder is shown.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
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
    """Dialog listing previously recorded sessions for replay, export, or deletion."""

    open_session = Signal(int)

    def __init__(self, repository: SessionRepository, parent: QWidget | None = None) -> None:
        """Initialise the browser dialog.

        Args:
            repository: The session repository to read from.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Sessions")
        self.resize(560, 460)
        self._repo = repository
        # A monotonically increasing token so a deferred load that
        # arrives after the user closed and reopened the dialog can
        # detect that it's stale and bail out.
        self._refresh_token = 0

        layout = QVBoxLayout(self)

        # Three pages: the session list, the empty-state placeholder,
        # and a "Loading..." page shown while the deferred read runs.
        # The stack keeps ``refresh`` to a single page-flip rather
        # than rebuilding the layout.
        self._stack = QStackedWidget()
        self._list = QListWidget()
        self._list.setObjectName("sessionList")
        self._list.setSpacing(2)
        self._empty = QLabel(
            "No saved sessions yet.\nStart one with the green button on "
            "the main window or with Ctrl+S."
        )
        self._empty.setObjectName("sessionListEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._loading = QLabel("Loading sessions...")
        self._loading.setObjectName("sessionListLoading")
        self._loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._list)
        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._loading)
        layout.addWidget(self._stack, 1)

        actions = QHBoxLayout()
        self._open = QPushButton("Open")
        self._rename = QPushButton("Rename...")
        self._delete = QPushButton("Delete")
        self._export = QPushButton("Export CSV...")
        actions.addWidget(self._open)
        actions.addWidget(self._rename)
        actions.addWidget(self._delete)
        actions.addWidget(self._export)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        layout.addWidget(buttons)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        self._open.clicked.connect(self._on_open)
        self._rename.clicked.connect(self._on_rename)
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
        """Re-read the session list from the database.

        The actual query runs on the next event-loop tick so the
        dialog can paint itself first. Users opening the browser see
        the window appear immediately with a "Loading..." placeholder
        while the read is in progress, instead of a frozen mouse
        cursor on a database with thousands of sessions.

        Calling ``refresh`` while a previous deferred load is still
        pending invalidates the older one through a token check.
        """
        self._refresh_token += 1
        token = self._refresh_token
        self._stack.setCurrentWidget(self._loading)
        self._refresh_action_buttons()
        # ``singleShot(0, ...)`` schedules the load for the next event
        # loop iteration, after the dialog's first paint event.
        QTimer.singleShot(0, lambda: self._populate(token))

    def _populate(self, token: int) -> None:
        """Run the session query and rebuild the rows.

        Args:
            token: The refresh token captured when this load was
                scheduled. If a newer refresh has been requested in
                the meantime the result is discarded.
        """
        if token != self._refresh_token:
            return
        try:
            sessions = list(self._repo.list_sessions())
        except Exception as exc:  # pragma: no cover - exercised by integration use
            self._loading.setText(f"Could not load sessions: {exc}")
            self._stack.setCurrentWidget(self._loading)
            return
        self._list.clear()
        for s in sessions:
            row = _SessionRow(s)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
        self._stack.setCurrentWidget(self._list if sessions else self._empty)
        self._refresh_action_buttons()

    def _refresh_action_buttons(self) -> None:
        """Enable the action buttons only when a row is selected."""
        has_selection = self._list.currentItem() is not None
        self._open.setEnabled(has_selection)
        self._rename.setEnabled(has_selection)
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

    def _on_rename(self) -> None:
        """Prompt for a new name and write it to the database."""
        sid = self._selected_session_id()
        if sid is None:
            return
        # Pre-fill with the current name from the selected row's title.
        item = self._list.currentItem()
        widget = self._list.itemWidget(item) if item is not None else None
        current = widget.session_name() if isinstance(widget, _SessionRow) else ""
        new_name, ok = QInputDialog.getText(
            self,
            "Rename session",
            "Session name (leave blank to clear):",
            text=current,
        )
        if not ok:
            return
        self._repo.rename_session(sid, new_name)
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


class _SessionRow(QWidget):
    """One session in the browser list.

    Two stacked text lines on the left, score badge on the right.
    The top line is the session name (or a fallback), the bottom
    line is the date plus a short metadata summary in dim text.
    """

    def __init__(self, summary: SessionSummary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sessionRow")
        # Keep the unmodified name so the rename dialog can pre-fill
        # the field with whatever the user previously typed (or an
        # empty string when the session was unnamed).
        self._session_name = summary.name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        text_block = QVBoxLayout()
        text_block.setContentsMargins(0, 0, 0, 0)
        text_block.setSpacing(2)

        title = QLabel(summary.name or f"Session #{summary.id}")
        title.setObjectName("sessionRowTitle")
        text_block.addWidget(title)

        meta = QLabel(_format_meta(summary))
        meta.setObjectName("sessionRowMeta")
        text_block.addWidget(meta)

        layout.addLayout(text_block, 1)

        score_text = _format_score(summary)
        if score_text:
            score = QLabel(score_text)
            score.setObjectName("sessionRowScore")
            score.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(score)

    def session_name(self) -> str:
        """Return the original session name (empty string when unnamed)."""
        return self._session_name

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(520, 56)


def _format_meta(summary: SessionSummary) -> str:
    """Return the dim secondary line. Date, shot count, duration."""
    started = summary.started_at.strftime("%d %b %Y, %H:%M").lstrip("0")
    shots = "1 shot" if summary.shot_count == 1 else f"{summary.shot_count} shots"
    return f"{started}  ·  {shots}  ·  {_format_duration(summary)}"


def _format_score(summary: SessionSummary) -> str:
    """Return the score badge text, or empty when there's nothing to show."""
    if summary.shot_count and summary.total_score > 0:
        return f"{summary.total_score:g} pts"
    return ""


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
