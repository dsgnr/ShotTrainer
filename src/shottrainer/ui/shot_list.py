"""The vertical shot list down the side of the window.

Each row shows the shot number, the score (if any), and how
far the shot landed from the target's centre. Designed for
quick visual scanning during a session and for clicking to
scrub the replay to a specific shot.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class ShotListEntry:
    index: int
    timestamp: float
    x_mm: float
    y_mm: float
    score: str | None = None


class ShotList(QWidget):
    shot_selected = Signal(int)  # entry index

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.setObjectName("shotList")
        self._list.setSpacing(2)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

    def set_shots(self, entries) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for e in entries:
            row = _ShotRow(
                index=e.index,
                score=getattr(e, "score", None),
                x_mm=getattr(e, "x_mm", 0.0),
                y_mm=getattr(e, "y_mm", 0.0),
            )
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, e.index)
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
        self._list.blockSignals(False)

    def select_index(self, index: int | None) -> None:
        if index is None:
            self._list.clearSelection()
            return
        if 0 <= index < self._list.count():
            self._list.setCurrentRow(index)

    def _on_selection_changed(self) -> None:
        items = self._list.selectedItems()
        if not items:
            return
        idx = items[0].data(Qt.ItemDataRole.UserRole)
        if isinstance(idx, int):
            self.shot_selected.emit(idx)


class _ShotRow(QWidget):
    """One shot in the list, showing its number, score badge and offset."""

    def __init__(
        self,
        index: int,
        score: str | None,
        x_mm: float,
        y_mm: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("shotRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        number = QLabel(f"#{index + 1}")
        number.setObjectName("shotRowNumber")
        number.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        number.setFixedWidth(36)
        layout.addWidget(number)

        score_label = QLabel(score or "-")
        score_label.setObjectName("shotRowScore")
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_label.setMinimumWidth(40)
        layout.addWidget(score_label)

        offset = QLabel(f"{x_mm:+5.1f}, {y_mm:+5.1f}\u202fmm")
        offset.setObjectName("shotRowOffset")
        offset.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        layout.addWidget(offset, 1)

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(220, 44)
