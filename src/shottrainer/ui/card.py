"""A floating panel card.

Each card has a small header label and a content area underneath. Cards
sit on a darker canvas with breathing room between them so the UI reads
as floating panels rather than a single uniform slab.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class Card(QFrame):
    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
        *,
        compact: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setProperty("card", True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        margin = 8 if compact else 14
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(8)

        if title:
            header = QLabel(title.upper())
            header.setObjectName("cardTitle")
            outer.addWidget(header)

        self._body_layout = QVBoxLayout()
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(8)
        outer.addLayout(self._body_layout, 1)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._body_layout.addWidget(widget, stretch)

    def add_row(self, *widgets: QWidget) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            row.addWidget(w)
        self._body_layout.addLayout(row)

    def add_layout(self, layout) -> None:
        self._body_layout.addLayout(layout)
