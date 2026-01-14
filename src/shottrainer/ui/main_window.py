"""Top-level application window. Kept small. Views compose into it."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ShotTrainer")
        self.resize(1024, 720)

        placeholder = QLabel("ShotTrainer\n\nCamera and tracking views land here.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)

        status = QStatusBar(self)
        status.showMessage("Ready")
        self.setStatusBar(status)
