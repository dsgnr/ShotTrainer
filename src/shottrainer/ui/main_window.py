"""The top-level application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .calibration_dialog import CalibrationDialog
from .camera_view import CameraView
from .preferences_dialog import Preferences, PreferencesDialog
from .replay_controls import ReplayControls
from .session_controls import SessionControls
from .shot_list import ShotList
from .target_view import TargetView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ShotTrainer")
        self.resize(1280, 820)

        self._prefs = Preferences()

        # Top control bar.
        self.session_controls = SessionControls()

        # Camera + target side by side, with shot list below the target.
        self.camera_view = CameraView()
        self.target_view = TargetView()
        self.shot_list = ShotList()

        target_column = QWidget()
        target_layout = QVBoxLayout(target_column)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addWidget(self.target_view, 3)
        target_layout.addWidget(self.shot_list, 2)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.camera_view)
        splitter.addWidget(target_column)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # Bottom replay strip.
        self.replay_controls = ReplayControls()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.session_controls)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.replay_controls)
        self.setCentralWidget(central)

        self._build_menus()

        status = QStatusBar(self)
        status.showMessage("Ready")
        self.setStatusBar(status)

        # Local UI wiring only. Service-level wiring happens elsewhere.
        self.shot_list.shot_selected.connect(self.target_view.set_selected_shot)

    def _build_menus(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        tools_menu = menu.addMenu("&Tools")
        calibrate_action = QAction("&Calibrate target...", self)
        calibrate_action.triggered.connect(self._open_calibration_dialog)
        tools_menu.addAction(calibrate_action)

        prefs_action = QAction("&Preferences...", self)
        prefs_action.triggered.connect(self._open_preferences_dialog)
        tools_menu.addAction(prefs_action)

    def _open_calibration_dialog(self) -> None:
        dialog = CalibrationDialog(parent=self)
        dialog.exec()

    def _open_preferences_dialog(self) -> None:
        dialog = PreferencesDialog(self._prefs, parent=self)
        dialog.saved.connect(self._on_preferences_saved)
        dialog.exec()

    def _on_preferences_saved(self, prefs: Preferences) -> None:
        self._prefs = prefs
        self.statusBar().showMessage(f"Saved preferences: camera {prefs.camera_id}", 3000)
