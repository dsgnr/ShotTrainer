"""The Preferences dialog with tabbed layout, live camera preview and target picker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .camera_view import CameraView
from .target_face_preview import TargetFacePreview
from .target_view import TargetRing


@dataclass(slots=True)
class Preferences:
    camera_id: int = 0
    camera_rotation: int = 0  # 0, 90, 180 or 270 degrees, clockwise
    camera_flip_h: bool = False
    camera_flip_v: bool = False
    audio_device: str = "default"
    audio_gain: float = 1.0
    shot_threshold: float = 0.25
    shot_refractory_ms: int = 400
    pre_shot_ms: int = 1500
    post_shot_ms: int = 800
    target_face: str = "default"
    shot_diameter_mm: float = 4.5  # air pellet by default; .22 ~= 5.6 mm
    tracking_region_fraction: float = 0.7


ROTATION_OPTIONS: tuple[tuple[int, str], ...] = (
    (0, "None"),
    (90, "90 clockwise"),
    (180, "180"),
    (270, "90 counter-clockwise"),
)


def _make_combo(
    items: list[tuple[object, str]],
    *,
    tooltip: str = "",
    initial: object | None = None,
) -> QComboBox:
    """Build a QComboBox whose popup view sizes to its longest entry."""
    combo = QComboBox()
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
    if tooltip:
        combo.setToolTip(tooltip)
    for value, label in items:
        combo.addItem(label, value)
    if initial is not None:
        idx = combo.findData(initial)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    # Make the popup wide enough to read the longest entry, regardless
    # of how narrow the combo itself is.
    metrics = combo.fontMetrics()
    max_w = max((metrics.horizontalAdvance(label) for _, label in items), default=120)
    combo.view().setMinimumWidth(max_w + 32)
    return combo


class PreferencesDialog(QDialog):
    saved = Signal(Preferences)

    def __init__(
        self,
        prefs: Preferences,
        camera_options: list[tuple[int, str]] | None = None,
        audio_options: list[str] | None = None,
        target_faces: list[tuple[str, str]] | None = None,
        rings_lookup: Callable[[str], tuple[TargetRing, ...]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(720, 540)
        self._prefs = prefs
        self._rings_lookup = rings_lookup

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_camera_tab(prefs, camera_options), "Camera")
        tabs.addTab(self._build_audio_tab(prefs, audio_options), "Audio")
        tabs.addTab(self._build_target_tab(prefs, target_faces), "Target")
        tabs.addTab(self._build_recording_tab(prefs), "Recording")
        tabs.addTab(self._build_about_tab(), "About")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

    def push_frame(self, frame_bgr: np.ndarray) -> None:
        """Called by the controller to update the embedded camera preview."""
        self._camera_preview.set_frame(frame_bgr)

    def push_audio_level(self, level: float) -> None:
        """Update the audio level meter (input is 0..1)."""
        v = round(min(1.0, max(0.0, level)) * 100)
        self._audio_meter.setValue(v)

    def _build_camera_tab(
        self,
        prefs: Preferences,
        camera_options: list[tuple[int, str]] | None,
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form = QFormLayout()
        cam_items = list(camera_options or [(0, "Camera 0")])
        self._camera = _make_combo(
            cam_items,
            tooltip="Webcam to use for tracking. Disconnect/reconnect a camera and reopen this dialog to refresh.",
            initial=prefs.camera_id,
        )
        form.addRow("Device", self._camera)

        self._rotation = _make_combo(
            list(ROTATION_OPTIONS),
            tooltip="Rotate the captured frame in 90 degree steps. Useful when a barrel-mounted camera is fitted sideways.",
            initial=prefs.camera_rotation,
        )
        form.addRow("Rotation", self._rotation)

        self._flip_h = QCheckBox("Mirror horizontally")
        self._flip_h.setChecked(prefs.camera_flip_h)
        self._flip_h.setToolTip("Flip the image left-right. Tick this if your trace moves opposite to your aim.")
        form.addRow("", self._flip_h)

        self._flip_v = QCheckBox("Mirror vertically")
        self._flip_v.setChecked(prefs.camera_flip_v)
        self._flip_v.setToolTip("Flip the image top-to-bottom. Useful when the camera is mounted upside down.")
        form.addRow("", self._flip_v)

        self._region = QDoubleSpinBox()
        self._region.setRange(0.1, 1.0)
        self._region.setSingleStep(0.05)
        self._region.setDecimals(2)
        self._region.setValue(prefs.tracking_region_fraction)
        self._region.setToolTip(
            "Fraction of the camera frame considered for tracking. Lower values "
            "ignore distractions near the edges. Higher values let the detector "
            "see more of the scene."
        )
        form.addRow("Tracking region", self._region)
        layout.addLayout(form)

        self._camera_preview = CameraView()
        self._camera_preview.setMinimumHeight(280)
        layout.addWidget(self._camera_preview, 1)
        layout.addWidget(QLabel("Live preview. Pick a camera to verify framing."))

        return page

    def _build_audio_tab(
        self,
        prefs: Preferences,
        audio_options: list[str] | None,
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        audio_items = [(name, name) for name in (audio_options or ["default"])]
        self._audio = _make_combo(
            audio_items,
            tooltip="Microphone used to detect shots.",
            initial=prefs.audio_device,
        )
        form.addRow("Input", self._audio)

        self._audio_gain = QDoubleSpinBox()
        self._audio_gain.setRange(0.1, 10.0)
        self._audio_gain.setSingleStep(0.1)
        self._audio_gain.setSuffix("x")
        self._audio_gain.setValue(prefs.audio_gain)
        self._audio_gain.setToolTip(
            "Software gain applied to the mic input before shot detection. "
            "Increase if a quiet shot doesn't register. Reduce if loud noises "
            "cause false triggers."
        )
        form.addRow("Volume", self._audio_gain)

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.01, 1.0)
        self._threshold.setSingleStep(0.01)
        self._threshold.setValue(prefs.shot_threshold)
        self._threshold.setToolTip(
            "Audio level above which a shot is registered (0..1). "
            "Watch the live level meter and pick a value just above the "
            "ambient noise."
        )
        form.addRow("Shot threshold", self._threshold)

        self._refractory = QSpinBox()
        self._refractory.setRange(50, 5000)
        self._refractory.setSuffix(" ms")
        self._refractory.setValue(prefs.shot_refractory_ms)
        self._refractory.setToolTip(
            "Time after a shot in which further triggers are ignored. "
            "Stops echoes and ringing being counted as extra shots."
        )
        form.addRow("Refractory window", self._refractory)
        layout.addLayout(form)

        meter_row = QHBoxLayout()
        meter_row.addWidget(QLabel("Live level"))
        self._audio_meter = QProgressBar()
        self._audio_meter.setRange(0, 100)
        self._audio_meter.setTextVisible(False)
        meter_row.addWidget(self._audio_meter, 1)
        layout.addLayout(meter_row)

        layout.addWidget(
            QLabel(
                "Lower the threshold if shots aren't detected. Raise it if loud "
                "ambient noise triggers false shots."
            )
        )
        layout.addStretch(1)
        return page

    def _build_target_tab(
        self,
        prefs: Preferences,
        target_faces: list[tuple[str, str]] | None,
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        face_items = list(target_faces or [("default", "Default rings")])
        self._target_face = _make_combo(
            face_items,
            tooltip="Scoring rings to draw on the target view. Doesn't change tracking. Only the visual reference.",
            initial=prefs.target_face,
        )
        form.addRow("Face", self._target_face)

        self._shot_diameter = QDoubleSpinBox()
        self._shot_diameter.setRange(0.5, 25.0)
        self._shot_diameter.setSingleStep(0.1)
        self._shot_diameter.setSuffix(" mm")
        self._shot_diameter.setValue(prefs.shot_diameter_mm)
        self._shot_diameter.setToolTip(
            "Pellet/bullet diameter. Used to draw shots at their correct size on "
            "the target view (4.5 mm for .177 air, 5.6 mm for .22)."
        )
        form.addRow("Shot diameter", self._shot_diameter)
        layout.addLayout(form)

        self._face_preview = TargetFacePreview()
        layout.addWidget(self._face_preview, 1)
        self._target_face.currentIndexChanged.connect(self._refresh_face_preview)
        self._refresh_face_preview()

        layout.addWidget(
            QLabel(
                "The selected face controls the scoring rings drawn on the "
                "target view. Calibration is independent of this choice."
            )
        )
        return page

    def _refresh_face_preview(self) -> None:
        if self._rings_lookup is None:
            return
        key = self._target_face.currentData()
        if not isinstance(key, str):
            return
        rings = self._rings_lookup(key)
        self._face_preview.set_rings(rings)

    def _build_recording_tab(self, prefs: Preferences) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        self._pre = QSpinBox()
        self._pre.setRange(0, 10000)
        self._pre.setSuffix(" ms")
        self._pre.setValue(prefs.pre_shot_ms)
        self._pre.setToolTip(
            "How much trace to keep before each shot. Used for hold-stability and "
            "tremor analysis on replay."
        )
        form.addRow("Pre-shot window", self._pre)

        self._post = QSpinBox()
        self._post.setRange(0, 10000)
        self._post.setSuffix(" ms")
        self._post.setValue(prefs.post_shot_ms)
        self._post.setToolTip(
            "How much trace to keep after each shot. Useful for follow-through "
            "review."
        )
        form.addRow("Post-shot window", self._post)
        layout.addLayout(form)

        layout.addWidget(
            QLabel(
                "These windows control how much trace is kept around each "
                "shot for replay."
            )
        )
        layout.addStretch(1)
        return page

    def _build_about_tab(self) -> QWidget:
        from shottrainer import __version__
        from shottrainer.ui.assets import asset_path

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        from PySide6.QtGui import QPixmap

        logo_label = QLabel()
        pixmap = QPixmap(str(asset_path("icon_128.png")))
        if not pixmap.isNull():
            logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)

        title = QLabel("ShotTrainer")
        title.setObjectName("aboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()
        form.addRow("Version", QLabel(__version__))
        form.addRow("Licence", QLabel("GPL-3.0-or-later"))
        layout.addLayout(form)

        blurb = QLabel(
            "ShotTrainer is open source. See the project README for the "
            "issue tracker and contribution guide."
        )
        blurb.setWordWrap(True)
        blurb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(blurb)

        layout.addStretch(1)
        return page

    def _on_save(self) -> None:
        cam_id = self._camera.currentData()
        rotation = self._rotation.currentData()
        audio = self._audio.currentText()
        target_face = self._target_face.currentData() or "default"
        updated = Preferences(
            camera_id=int(cam_id) if cam_id is not None else 0,
            camera_rotation=int(rotation) if rotation is not None else 0,
            camera_flip_h=self._flip_h.isChecked(),
            camera_flip_v=self._flip_v.isChecked(),
            audio_device=audio,
            audio_gain=float(self._audio_gain.value()),
            shot_threshold=float(self._threshold.value()),
            shot_refractory_ms=int(self._refractory.value()),
            pre_shot_ms=int(self._pre.value()),
            post_shot_ms=int(self._post.value()),
            target_face=str(target_face),
            shot_diameter_mm=float(self._shot_diameter.value()),
            tracking_region_fraction=float(self._region.value()),
        )
        self.saved.emit(updated)
        self.accept()
