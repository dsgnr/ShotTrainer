"""The top-level application window. Just UI scaffolding, no domain logic."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .app_header import AppHeader
from .audio_meter import AudioMeter
from .camera_view import CameraView
from .hero_stats import HeroStats
from .marker_sheet import MarkerSheetDialog
from .preferences_dialog import Preferences, PreferencesDialog
from .replay_controls import ReplayControls
from .session_controls import SessionControls
from .shot_list import ShotList
from .stats_panel import StatsPanel
from .target_view import TargetView
from .zoom_controls import ZoomControls


class MainWindow(QMainWindow):
    """The window. The controller is what actually does the work."""

    preferences_changed = Signal(object)  # Preferences
    session_browser_requested = Signal()
    preferences_dialog_opened = Signal(object)  # PreferencesDialog
    zero_on_aim_requested = Signal()
    zero_cleared = Signal()
    rescore_requested = Signal()
    circle_diameter_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ShotTrainer")
        self.resize(1440, 880)

        self._prefs = Preferences()
        self._device_options_provider: Callable | None = None
        self._saved_camera_name_provider: Callable | None = None
        self._target_faces_provider: Callable | None = None
        self._rings_lookup: Callable | None = None
        self._face_lookup: Callable | None = None
        self._is_recording_check: Callable[[], bool] = lambda: False

        self.header = AppHeader()
        self.header.settings_button.clicked.connect(self._open_preferences_dialog)

        self.session_controls = SessionControls()
        self.camera_view = CameraView()
        self.target_view = TargetView()
        self.shot_list = ShotList()
        self.hero_stats = HeroStats()
        self.stats_panel = StatsPanel()  # built but not displayed. Kept for the controller
        self.audio_meter = AudioMeter()
        self.zoom_controls = ZoomControls()
        self.zoom_controls.set_extent(self.target_view.extent_mm)
        self.zoom_controls.extent_changed.connect(self.target_view.set_extent_mm)
        self.target_view.extent_changed.connect(self.zoom_controls.set_extent)
        self.replay_controls = ReplayControls()

        self._zero_button = QPushButton("Zero on aim")
        self._zero_button.setToolTip(
            "Lock the current aim point as the trace's (0, 0). Hold the "
            "rifle on the target's centre and click."
        )
        self._zero_button.clicked.connect(self.zero_on_aim_requested)

        self._clear_zero_button = QPushButton("Clear zero")
        self._clear_zero_button.setToolTip(
            "Remove the user-set zero offset and report aim relative to "
            "the live circle's centre again."
        )
        self._clear_zero_button.clicked.connect(self.zero_cleared)
        self._clear_zero_button.setEnabled(False)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(0)
        splitter.addWidget(self._build_left_column())
        splitter.addWidget(self._build_centre_column())
        splitter.addWidget(self._build_right_column())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([260, 880, 300])
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

        self.shot_list.shot_selected.connect(self.target_view.set_selected_shot)
        self._install_shortcuts()

    def _build_left_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("leftColumn")
        col.setMinimumWidth(220)
        col.setMaximumWidth(320)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(20, 24, 12, 24)
        layout.setSpacing(20)

        layout.addWidget(self._caption_label("CAMERA"))
        self.camera_view.setMinimumSize(220, 165)
        self.camera_view.setMaximumHeight(220)
        layout.addWidget(self.camera_view)

        zero_row = QHBoxLayout()
        zero_row.setContentsMargins(0, 0, 0, 0)
        zero_row.setSpacing(8)
        zero_row.addWidget(self._zero_button)
        zero_row.addWidget(self._clear_zero_button)
        layout.addLayout(zero_row)

        layout.addSpacing(12)
        layout.addWidget(self._caption_label("MIC LEVEL"))
        layout.addWidget(self.audio_meter)
        layout.addStretch(1)
        return col

    def _build_centre_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("centreColumn")
        layout = QVBoxLayout(col)
        layout.setContentsMargins(12, 24, 12, 16)
        layout.setSpacing(16)

        layout.addWidget(self.target_view, 1)

        # Compact zoom + replay row sits directly under the target. No
        # surrounding chrome. Spacing alone groups them with the target.
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(8, 0, 8, 0)
        controls_row.setSpacing(20)
        controls_row.addWidget(self.zoom_controls, 1)
        controls_row.addSpacing(8)
        controls_row.addWidget(self.replay_controls, 1)
        layout.addLayout(controls_row)
        return col

    def _build_right_column(self) -> QWidget:
        col = QFrame()
        col.setObjectName("rightColumn")
        col.setMinimumWidth(280)
        col.setMaximumWidth(380)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(12, 24, 24, 24)
        layout.setSpacing(20)

        layout.addWidget(self._caption_label("RESULTS"))
        layout.addWidget(self.hero_stats)

        layout.addSpacing(12)
        layout.addWidget(self._caption_label("SHOTS"))
        layout.addWidget(self.shot_list, 1)

        layout.addWidget(self._caption_label("SESSION"))
        layout.addWidget(self.session_controls)
        return col

    def _caption_label(self, text: str):
        from PySide6.QtWidgets import QLabel

        label = QLabel(text)
        label.setObjectName("columnCaption")
        return label

    def set_tracking_status(self, text: str) -> None:
        """Update the header's secondary status line (live mm/px and so on)."""
        self.header.set_status_text(text)

    def set_zero_offset_state(
        self,
        has_offset: bool,
        offset_mm: tuple[float, float] | None = None,
    ) -> None:
        """Reflect the current zero offset in the UI.

        ``has_offset`` enables the "Clear zero" button.
        ``offset_mm`` is only used for the button's tooltip so
        the user can see what's being applied.
        """
        self._clear_zero_button.setEnabled(has_offset)
        if has_offset and offset_mm is not None:
            self._zero_button.setToolTip(
                f"Current zero offset: ({offset_mm[0]:.1f}, {offset_mm[1]:.1f}) mm. "
                "Click to lock the current aim as the new origin."
            )
        else:
            self._zero_button.setToolTip(
                "Lock the current aim point as the trace's (0, 0). Hold the "
                "rifle on the target's centre and click."
            )

    def main_splitter_sizes(self) -> list[int]:
        return list(self._main_splitter.sizes())

    def restore_main_splitter_sizes(self, sizes: list[int]) -> None:
        if sizes and len(sizes) == self._main_splitter.count():
            self._main_splitter.setSizes(sizes)

    def set_device_options_provider(self, fn: Callable) -> None:
        self._device_options_provider = fn

    def set_saved_camera_name_provider(self, fn: Callable) -> None:
        """Provide a ``() -> str`` callable returning the saved camera's name.

        Used by the Preferences dialog so the device combo can
        match the saved camera by name across changes in
        enumeration order (someone plugs in a new USB camera
        that shifts the indices).
        """
        self._saved_camera_name_provider = fn

    def set_target_faces_provider(self, fn: Callable) -> None:
        self._target_faces_provider = fn

    def set_rings_lookup(self, fn: Callable) -> None:
        self._rings_lookup = fn

    def set_face_lookup(self, fn: Callable) -> None:
        """Provide a ``(key) -> TargetFace | None`` callable.

        Used by the Preferences dialog to auto-populate the
        calibre and tracking-circle fields when the user picks
        a different face. Optional. Without it the face combo
        still works but the spinboxes don't auto-fill.
        """
        self._face_lookup = fn

    def set_recording_check(self, fn: Callable[[], bool]) -> None:
        """Hook for the controller to tell the window whether a session is live.

        Used by the close prompt. Defaults to "not recording"
        so the window can be tested in isolation without a
        controller.
        """
        self._is_recording_check = fn

    def current_preferences(self) -> Preferences:
        return self._prefs

    def set_current_preferences(self, prefs: Preferences) -> None:
        """Replace the cached preferences the dialog will show next time.

        The controller calls this whenever its authoritative
        copy changes (load-from-disk at startup, the settings
        watcher reloading the file, the marker-sheet dialog
        editing the circle diameter) so the Preferences dialog
        always opens against current values, not the stale
        defaults this window started with.
        """
        self._prefs = prefs

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
        prefs_action = QAction("&Preferences...", self)
        prefs_action.triggered.connect(self._open_preferences_dialog)
        tools_menu.addAction(prefs_action)

        marker_action = QAction("Print &marker sheet...", self)
        marker_action.triggered.connect(self._open_marker_sheet_dialog)
        tools_menu.addAction(marker_action)

        tools_menu.addSeparator()

        rescore_action = QAction("&Re-score with current face", self)
        rescore_action.setToolTip(
            "Re-evaluate every shot in view against the currently selected "
            "target face. Useful after switching faces on a loaded session."
        )
        rescore_action.triggered.connect(self.rescore_requested)
        tools_menu.addAction(rescore_action)

    def _open_marker_sheet_dialog(self) -> None:
        """Open the marker-sheet print dialog and propagate any diameter change.

        Keeps Preferences (and the live tracker) in sync with
        whatever value the user picked in the dialog.
        """
        dialog = MarkerSheetDialog(
            diameter_mm=self._prefs.circle_diameter_mm,
            parent=self,
        )
        dialog.exec()
        chosen = dialog.diameter_mm()
        if abs(chosen - self._prefs.circle_diameter_mm) > 1e-6:
            self._prefs.circle_diameter_mm = chosen
            self.circle_diameter_changed.emit(chosen)

    def _open_preferences_dialog(self) -> None:
        cameras: list[tuple[int, str]] | None = None
        microphones: list[str] | None = None
        if self._device_options_provider is not None:
            cameras, microphones = self._device_options_provider()
        target_faces: list[tuple[str, str]] | None = None
        if self._target_faces_provider is not None:
            target_faces = self._target_faces_provider()
        saved_camera_name = ""
        if self._saved_camera_name_provider is not None:
            saved_camera_name = self._saved_camera_name_provider() or ""
        dialog = PreferencesDialog(
            self._prefs,
            camera_options=cameras,
            audio_options=microphones,
            target_faces=target_faces,
            rings_lookup=self._rings_lookup,
            face_lookup=self._face_lookup,
            saved_camera_name=saved_camera_name,
            parent=self,
        )
        dialog.saved.connect(self._on_preferences_saved)
        self.preferences_dialog_opened.emit(dialog)
        dialog.exec()

    def _on_preferences_saved(self, prefs: Preferences) -> None:
        self._prefs = prefs
        cam_text = (
            "no camera" if prefs.camera_id is None else f"camera {prefs.camera_id}"
        )
        self.statusBar().showMessage(f"Saved preferences: {cam_text}", 3000)
        self.preferences_changed.emit(prefs)

    def _install_shortcuts(self) -> None:
        """Set up the keyboard shortcuts.

        The same actions are always reachable through buttons
        and menus too. The shortcuts are for users who prefer
        muscle memory.
        """
        toggle = QShortcut(QKeySequence("Ctrl+S"), self)
        toggle.activated.connect(self._toggle_session)
        clear = QShortcut(QKeySequence("Ctrl+R"), self)
        clear.activated.connect(self._invoke_clear_shots)
        space = QShortcut(QKeySequence("Space"), self)
        space.activated.connect(self._toggle_replay)

    def _toggle_session(self) -> None:
        self.session_controls.primary_action().click()

    def _invoke_clear_shots(self) -> None:
        if self.session_controls.clear_button().isEnabled():
            self.session_controls.clear_shots_requested.emit()

    def _toggle_replay(self) -> None:
        # Don't intercept space when an input has focus.
        focus = self.focusWidget()
        if focus is not None and focus.metaObject().className() in (
            "QLineEdit",
            "QSpinBox",
            "QDoubleSpinBox",
            "QComboBox",
        ):
            return
        if self.replay_controls.isEnabled():
            self.replay_controls.play_clicked.emit()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Prompt before closing if a session is in progress."""
        if not self._is_recording_check():
            super().closeEvent(event)
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Session in progress")
        box.setText("A recording session is still active.")
        box.setInformativeText(
            "Stop and save the session before quitting, or quit anyway "
            "and let the controller flush whatever's in flight."
        )
        stop_btn = box.addButton("Stop and quit", QMessageBox.ButtonRole.AcceptRole)
        quit_btn = box.addButton("Quit anyway", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("Keep recording", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is stop_btn:
            self.session_controls.stop_requested.emit()
            super().closeEvent(event)
        elif clicked is quit_btn:
            super().closeEvent(event)
        else:
            event.ignore()
