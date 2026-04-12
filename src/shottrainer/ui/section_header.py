"""Small section header used above each side-panel block."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


class SectionHeader(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidePanelHeader")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        label = QLabel(title.upper())
        layout.addWidget(label)
