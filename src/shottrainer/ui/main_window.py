"""The top-level application window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QLabel,
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
    preferences_changed = Signal(object)  # Preferences
    session_browser_requested = Signal()
    calibration_points_accepted = Signal(list)
    calibration_dialog_opened = Signal(object)  # CalibrationDialog

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ShotTrainer")
        self.resize(1280, 820)

        self._prefs = Preferences()
        self._calibration_corner_detector: Callable | None = None
        self._device_options_provider: Callable | None = None

        self.session_controls = SessionControls()
        self.camera_view = CameraView()
        self.target_view = TargetView()
        self.shot_list = ShotList()

        # Layout: target view dominates the main area. The camera preview
        # and shot list sit in a slimmer side column. The camera preview is
        # still useful for verifying tracking, but the user's eyes belong on
        # the target.
        side_column = QWidget()
        side_layout = QVBoxLayout(side_column)
        side_layout.setContentsMargins(0, 0, 0, 0)
        self.camera_view.setMinimumSize(240, 180)
        self.camera_view.setMaximumHeight(260)
        side_layout.addWidget(self.camera_view, 1)
        side_layout.addWidget(self.shot_list, 2)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.target_view)
        splitter.addWidget(side_column)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 320])

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

        self._calibration_label = QLabel("Uncalibrated")
        status.addPermanentWidget(self._calibration_label)

        self.shot_list.shot_selected.connect(self.target_view.set_selected_shot)

    def set_calibration_status(self, text: str) -> None:
        self._calibration_label.setText(text)

    def set_calibration_corner_detector(self, fn: Callable) -> None:
        self._calibration_corner_detector = fn

    def set_device_options_provider(self, fn: Callable) -> None:
        """Provider returns ``(cameras, microphones)`` to populate the dialog."""
        self._device_options_provider = fn

    def current_preferences(self) -> Preferences:
        return self._prefs

    def _build_menus(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        sessions_action = QAction("&Sessions...", self)
        sessions_action.triggered.connect(self.session_browser_requested)
        file_menu.addAction(sessions_action)
        file_menu.addSeparator()
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
        dialog = CalibrationDialog(detect_corners=self._calibration_corner_detector, parent=self)
        dialog.accepted_points.connect(self.calibration_points_accepted)
        self.calibration_dialog_opened.emit(dialog)
        dialog.exec()

    def _open_preferences_dialog(self) -> None:
        cameras: list[tuple[int, str]] | None = None
        microphones: list[str] | None = None
        if self._device_options_provider is not None:
            cameras, microphones = self._device_options_provider()
        dialog = PreferencesDialog(
            self._prefs,
            camera_options=cameras,
            audio_options=microphones,
            parent=self,
        )
        dialog.saved.connect(self._on_preferences_saved)
        dialog.exec()

    def _on_preferences_saved(self, prefs: Preferences) -> None:
        self._prefs = prefs
        self.statusBar().showMessage(f"Saved preferences: camera {prefs.camera_id}", 3000)
        self.preferences_changed.emit(prefs)
