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
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from shottrainer.services.exporter import export_session_csv
from shottrainer.sessions.models import SESSION_CATEGORIES
from shottrainer.sessions.repository import SessionRepository, SessionSummary
from shottrainer.ui.assets import asset_path

_CATEGORY_ICON_FILES = {
    "practice": "category_practice.svg",
    "sighter": "category_sighter.svg",
    "match": "category_match.svg",
}


def _category_icon(category: str, size: int = 20) -> QPixmap | None:
    """Render the icon for a category to a transparent pixmap.

    Returns ``None`` when the category is unknown or the asset file
    is missing, so the caller can fall back to no icon at all.
    """
    filename = _CATEGORY_ICON_FILES.get(category)
    if filename is None:
        return None
    path = asset_path(filename)
    if not path.exists():
        return None
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return None
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return pix


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
        # Raw list of summaries from the most recent load. Filtering
        # works against this cache so typing in the search field
        # doesn't trigger another database query.
        self._all_sessions: list[SessionSummary] = []

        layout = QVBoxLayout(self)

        # Search and category filter row at the top of the dialog.
        # Both inputs filter the list in-memory against ``_all_sessions``
        # so the user gets instant feedback while typing.
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search session names...")
        self._search.setClearButtonEnabled(True)
        filter_row.addWidget(self._search, 1)
        self._category_filter = QComboBox()
        self._category_filter.addItem("All categories", "")
        for value in SESSION_CATEGORIES:
            self._category_filter.addItem(value.capitalize(), value)
        filter_row.addWidget(self._category_filter)
        layout.addLayout(filter_row)

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
        self._category = QPushButton("Category...")
        self._delete = QPushButton("Delete")
        self._export = QPushButton("Export CSV...")
        actions.addWidget(self._open)
        actions.addWidget(self._rename)
        actions.addWidget(self._category)
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
        self._category.clicked.connect(self._on_category)
        self._delete.clicked.connect(self._on_delete)
        self._export.clicked.connect(self._on_export)

        # Open / Delete / Export only make sense with a row
        # selected. Bind their enabled state to the list's
        # selection so the dialog isn't offering buttons that
        # would do nothing.
        self._list.itemDoubleClicked.connect(lambda _item: self._on_open())
        self._list.currentItemChanged.connect(lambda *_: self._refresh_action_buttons())

        # Filtering re-renders the list against the cached summaries
        # without going back to the database.
        self._search.textChanged.connect(lambda *_: self._apply_filter())
        self._category_filter.currentIndexChanged.connect(lambda *_: self._apply_filter())

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
        self._all_sessions = sessions
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Render the cached session list under the current filters.

        Called both after a fresh database read and when the user
        types in the search field or picks a different category.
        """
        query = self._search.text().strip().lower()
        category = self._category_filter.currentData() or ""
        matches = [
            s
            for s in self._all_sessions
            if (not query or query in s.name.lower()) and (not category or s.category == category)
        ]

        self._list.clear()
        for s in matches:
            row = _SessionRow(s)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

        if matches:
            self._stack.setCurrentWidget(self._list)
        else:
            if not self._all_sessions:
                self._empty.setText(
                    "No saved sessions yet.\nStart one with the green button on "
                    "the main window or with Ctrl+S."
                )
            else:
                self._empty.setText(
                    "No sessions match your filter.\nTry a different name or category."
                )
            self._stack.setCurrentWidget(self._empty)
        self._refresh_action_buttons()

    def _refresh_action_buttons(self) -> None:
        """Enable the action buttons only when a row is selected."""
        has_selection = self._list.currentItem() is not None
        self._open.setEnabled(has_selection)
        self._rename.setEnabled(has_selection)
        self._category.setEnabled(has_selection)
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

    def _on_category(self) -> None:
        """Prompt for a new category and write it to the database."""
        sid = self._selected_session_id()
        if sid is None:
            return
        item = self._list.currentItem()
        widget = self._list.itemWidget(item) if item is not None else None
        current = widget.session_category() if isinstance(widget, _SessionRow) else ""
        # ``SESSION_CATEGORIES`` is a tuple so cast to a list for the
        # dialog. The display label uses Title Case while the stored
        # value stays lowercase.
        choices = list(SESSION_CATEGORIES)
        labels = [c.capitalize() for c in choices]
        try:
            current_index = choices.index(current)
        except ValueError:
            current_index = 0
        chosen_label, ok = QInputDialog.getItem(
            self,
            "Set category",
            "Category:",
            labels,
            current_index,
            editable=False,
        )
        if not ok:
            return
        chosen = choices[labels.index(chosen_label)]
        self._repo.update_session_category(sid, chosen)
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
        self._session_category = summary.category

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

        # Category icon sits to the left of the score so the score
        # always stays at the right edge of the row. The tooltip
        # carries the category name so screen readers and hover
        # users still see the label even though the icon is silent.
        if summary.category:
            icon_pixmap = _category_icon(summary.category)
            if icon_pixmap is not None:
                badge = QLabel()
                badge.setPixmap(icon_pixmap)
                badge.setObjectName("sessionRowCategory")
                badge.setProperty("category", summary.category)
                badge.setToolTip(summary.category.capitalize())
                badge.setAccessibleName(f"{summary.category.capitalize()} session")
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(badge)

        score_text = _format_score(summary)
        if score_text:
            score = QLabel(score_text)
            score.setObjectName("sessionRowScore")
            score.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(score)

    def session_name(self) -> str:
        """Return the original session name (empty string when unnamed)."""
        return self._session_name

    def session_category(self) -> str:
        """Return the session's category tag."""
        return self._session_category

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
