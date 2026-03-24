"""The top-level application window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .app_header import AppHeader
from .audio_meter import AudioMeter
from .calibration_dialog import CalibrationDialog
from .camera_view import CameraView
from .card import Card
from .marker_sheet import MarkerSheetDialog
from .preferences_dialog import Preferences, PreferencesDialog
from .replay_controls import ReplayControls
from .session_controls import SessionControls
from .shot_list import ShotList
from .stats_panel import StatsPanel
from .target_view import TargetView
from .zoom_controls import ZoomControls


class MainWindow(QMainWindow):
    preferences_changed = Signal(object)  # Preferences
    session_browser_requested = Signal()
    calibration_points_accepted = Signal(list)
    calibration_dialog_opened = Signal(object)  # CalibrationDialog
    preferences_dialog_opened = Signal(object)  # PreferencesDialog
    manual_aim_requested = Signal(float, float)  # image-space px
    manual_aim_cleared = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ShotTrainer")
        self.resize(1440, 880)

        self._prefs = Preferences()
        self._calibration_corner_detector: Callable | None = None
        self._device_options_provider: Callable | None = None
        self._target_faces_provider: Callable | None = None
        self._rings_lookup: Callable | None = None

        # Header. Cross-cutting state and the only entry to settings.
        self.header = AppHeader()
        self.header.settings_button.clicked.connect(self._open_preferences_dialog)

        # Core widgets
        self.session_controls = SessionControls()
        self.camera_view = CameraView()
        self.target_view = TargetView()
        self.shot_list = ShotList()
        self.stats_panel = StatsPanel()
        self.audio_meter = AudioMeter()
        self.zoom_controls = ZoomControls()
        self.zoom_controls.set_extent(self.target_view.extent_mm)
        self.zoom_controls.extent_changed.connect(self.target_view.set_extent_mm)
        self.target_view.extent_changed.connect(self.zoom_controls.set_extent)
        self.replay_controls = ReplayControls()

        # Manual aim toggle, used in the camera column.
        self._manual_aim_button = QPushButton("Pick aim manually")
        self._manual_aim_button.setCheckable(True)
        self._manual_aim_button.toggled.connect(self._on_manual_aim_toggled)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_column())
        splitter.addWidget(self._build_centre_column())
        splitter.addWidget(self._build_right_column())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([320, 800, 320])
        self._main_splitter = splitter

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self._build_menus()

        status = QStatusBar(self)
        status.showMessage("Ready")
        self.setStatusBar(status)

        self._calibration_label = QLabel("Uncalibrated")
        status.addPermanentWidget(self._calibration_label)

        self.shot_list.shot_selected.connect(self.target_view.set_selected_shot)
        self.camera_view.clicked_at.connect(self._on_camera_view_clicked)

    def _build_left_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("leftColumn")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(12, 12, 6, 12)
        layout.setSpacing(12)

        camera_card = Card("Camera")
        self.camera_view.setMinimumSize(280, 200)
        camera_card.add_widget(self.camera_view, stretch=1)
        camera_card.add_widget(self._manual_aim_button)
        layout.addWidget(camera_card, 2)

        mic_card = Card("Microphone")
        mic_card.add_widget(self.audio_meter)
        layout.addWidget(mic_card)

        layout.addStretch(1)
        return col

    def _build_centre_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("centreColumn")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(6, 12, 6, 12)
        layout.setSpacing(12)

        target_card = Card()
        target_card.add_widget(self.target_view, stretch=1)
        layout.addWidget(target_card, 1)

        controls_card = Card(compact=True)
        controls_card.add_widget(self.zoom_controls)
        controls_card.add_widget(self.replay_controls)
        layout.addWidget(controls_card)
        return col

    def _build_right_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("rightColumn")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(6, 12, 12, 12)
        layout.setSpacing(12)

        session_card = Card("Session")
        session_card.add_widget(self.session_controls)
        layout.addWidget(session_card)

        shots_card = Card("Shots")
        shots_card.add_widget(self.shot_list, stretch=1)
        layout.addWidget(shots_card, 1)

        stats_card = Card("Stats")
        stats_card.add_widget(self.stats_panel)
        layout.addWidget(stats_card)
        return col

    def set_calibration_status(self, text: str) -> None:
        self._calibration_label.setText(text)

    def main_splitter_sizes(self) -> list[int]:
        return list(self._main_splitter.sizes())

    def restore_main_splitter_sizes(self, sizes: list[int]) -> None:
        if sizes and len(sizes) == self._main_splitter.count():
            self._main_splitter.setSizes(sizes)

    def set_calibration_corner_detector(self, fn: Callable) -> None:
        self._calibration_corner_detector = fn

    def set_device_options_provider(self, fn: Callable) -> None:
        """Provider returns ``(cameras, microphones)`` to populate the dialog."""
        self._device_options_provider = fn

    def set_target_faces_provider(self, fn: Callable) -> None:
        """Provider returns a list of ``(key, label)`` for target face choices."""
        self._target_faces_provider = fn

    def set_rings_lookup(self, fn: Callable) -> None:
        self._rings_lookup = fn

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

        marker_action = QAction("Print &marker sheet...", self)
        marker_action.triggered.connect(self._open_marker_sheet_dialog)
        tools_menu.addAction(marker_action)

    def _open_calibration_dialog(self) -> None:
        dialog = CalibrationDialog(detect_corners=self._calibration_corner_detector, parent=self)
        dialog.accepted_points.connect(self.calibration_points_accepted)
        self.calibration_dialog_opened.emit(dialog)
        dialog.exec()

    def _open_marker_sheet_dialog(self) -> None:
        dialog = MarkerSheetDialog(parent=self)
        dialog.exec()

    def _open_preferences_dialog(self) -> None:
        cameras: list[tuple[int, str]] | None = None
        microphones: list[str] | None = None
        if self._device_options_provider is not None:
            cameras, microphones = self._device_options_provider()
        target_faces: list[tuple[str, str]] | None = None
        if self._target_faces_provider is not None:
            target_faces = self._target_faces_provider()
        dialog = PreferencesDialog(
            self._prefs,
            camera_options=cameras,
            audio_options=microphones,
            target_faces=target_faces,
            rings_lookup=self._rings_lookup,
            parent=self,
        )
        dialog.saved.connect(self._on_preferences_saved)
        self.preferences_dialog_opened.emit(dialog)
        dialog.exec()

    def _on_preferences_saved(self, prefs: Preferences) -> None:
        self._prefs = prefs
        self.statusBar().showMessage(f"Saved preferences: camera {prefs.camera_id}", 3000)
        self.preferences_changed.emit(prefs)

    def _on_manual_aim_toggled(self, checked: bool) -> None:
        if checked:
            self._manual_aim_button.setText("Manual aim ON (click image)")
            self.statusBar().showMessage("Click the camera view to set the aim point", 4000)
        else:
            self._manual_aim_button.setText("Pick aim manually")
            self.manual_aim_cleared.emit()

    def _on_camera_view_clicked(self, x: float, y: float) -> None:
        if self._manual_aim_button.isChecked():
            self.manual_aim_requested.emit(x, y)
