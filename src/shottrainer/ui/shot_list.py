"""Shot list panel.

Shows the shots in the current session, with a small badge for each. The
panel is intentionally read-only. Selection is reported via a signal so the
main window can drive the target view and replay controls.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget


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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

    def set_shots(self, entries: list[ShotListEntry]) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for e in entries:
            label = f"#{e.index + 1:>2}  ({e.x_mm:+6.1f}, {e.y_mm:+6.1f}) mm"
            if e.score:
                label += f"   {e.score}"
            item = QListWidgetItem(label)
            item.setData(0x0100, e.index)  # Qt.UserRole
            self._list.addItem(item)
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
        idx = items[0].data(0x0100)
        if isinstance(idx, int):
            self.shot_selected.emit(idx)
