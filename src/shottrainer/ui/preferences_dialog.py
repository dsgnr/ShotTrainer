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
    QPushButton,
    QSizePolicy,
    QSlider,
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
    camera_brightness: float | None = None
    camera_contrast: float | None = None
    camera_saturation: float | None = None
    camera_gain: float | None = None
    camera_exposure: float | None = None
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


CALIBRES_MM: dict[str, float] = {
    "177": 4.5,
    "20": 5.0,
    "22": 5.6,
    "25": 6.35,
    "9mm": 9.0,
    "45": 11.43,
}


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
    optimise_requested = Signal()
    reset_detector_requested = Signal()
    camera_property_changed = Signal(str, object)

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
        """Called by the controller to update the embedded preview.

        The dialog applies the *current* (unsaved) rotation and flip
        choices so the preview reflects what saving will do.
        """
        self._latest_raw_frame = frame_bgr
        self._refresh_preview_frame()

    def _refresh_preview_frame(self) -> None:
        from shottrainer.tracking.frame_ops import transform_frame

        frame = getattr(self, "_latest_raw_frame", None)
        if frame is None:
            return
        rotation = self._rotation.currentData() or 0
        try:
            transformed = transform_frame(
                frame,
                rotation_degrees=int(rotation),
                flip_horizontal=self._flip_h.isChecked(),
                flip_vertical=self._flip_v.isChecked(),
            )
        except Exception:
            transformed = frame
        self._camera_preview.set_frame(transformed)
        self._camera_preview.set_region_fraction(float(self._region.value()))

    def _on_region_preview_changed(self, _value: float) -> None:
        self._camera_preview.set_region_fraction(float(self._region.value()))

    def push_audio_level(self, level: float) -> None:
        """Update the audio level meter (input is 0..1)."""
        v = round(min(1.0, max(0.0, level)) * 100)
        self._audio_meter.setValue(v)

    def set_camera_property_actual(self, name: str, value: float | None) -> None:
        """Surface the camera's reported value for a property.

        OpenCV reports a normalised value back. We pass it on as-is so
        the user can see what the driver actually accepted. The value is
        appended to the slider's tooltip. The slider position itself
        is the user's request.
        """
        slider = getattr(self, f"_{name}", None)
        if slider is None:
            return
        if value is None:
            slider.setToolTip(slider.toolTip().split("\n")[0])
            return
        base = slider.toolTip().split("\n")[0]
        slider.setToolTip(f"{base}\nCamera reports: {value:.2f}")

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
        self._rotation.currentIndexChanged.connect(lambda _i: self._refresh_preview_frame())
        form.addRow("Rotation", self._rotation)

        self._flip_h = QCheckBox("Mirror horizontally")
        self._flip_h.setChecked(prefs.camera_flip_h)
        self._flip_h.setToolTip("Flip the image left-right. Tick this if your trace moves opposite to your aim.")
        self._flip_h.toggled.connect(lambda _v: self._refresh_preview_frame())
        form.addRow("", self._flip_h)

        self._flip_v = QCheckBox("Mirror vertically")
        self._flip_v.setChecked(prefs.camera_flip_v)
        self._flip_v.setToolTip("Flip the image top-to-bottom. Useful when the camera is mounted upside down.")
        self._flip_v.toggled.connect(lambda _v: self._refresh_preview_frame())
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
        self._region.valueChanged.connect(self._on_region_preview_changed)
        form.addRow("Tracking region", self._region)

        # Hardware image controls. Each slider has an "auto" checkbox that
        # leaves the camera at its default value.
        self._brightness, b_row = self._make_property_slider(
            "brightness", prefs.camera_brightness, "Brightness"
        )
        form.addRow("Brightness", b_row)
        self._contrast, c_row = self._make_property_slider(
            "contrast", prefs.camera_contrast, "Contrast"
        )
        form.addRow("Contrast", c_row)
        self._saturation, s_row = self._make_property_slider(
            "saturation", prefs.camera_saturation, "Saturation"
        )
        form.addRow("Saturation", s_row)
        self._gain, g_row = self._make_property_slider(
            "gain", prefs.camera_gain, "Gain"
        )
        form.addRow("Gain", g_row)
        self._exposure, e_row = self._make_property_slider(
            "exposure", prefs.camera_exposure, "Exposure"
        )
        form.addRow("Exposure", e_row)

        layout.addLayout(form)

        self._optimise_btn = QPushButton("Auto-optimise tracking")
        self._optimise_btn.setToolTip(
            "Sample the current frame and pick detector thresholds that find the "
            "target most reliably. Re-run if lighting or framing changes."
        )
        self._optimise_btn.clicked.connect(self.optimise_requested)

        self._reset_detector_btn = QPushButton("Reset")
        self._reset_detector_btn.setToolTip(
            "Discard auto-optimised detector settings and go back to the defaults."
        )
        self._reset_detector_btn.clicked.connect(self.reset_detector_requested)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addWidget(self._optimise_btn, 1)
        button_row.addWidget(self._reset_detector_btn)
        layout.addLayout(button_row)

        self._camera_preview = CameraView()
        self._camera_preview.setMinimumHeight(280)
        self._camera_preview.set_region_fraction(prefs.tracking_region_fraction)
        layout.addWidget(self._camera_preview, 1)
        layout.addWidget(QLabel("Live preview. Pick a camera to verify framing."))

        return page

    def _make_property_slider(
        self, name: str, value: float | None, label: str
    ) -> tuple[QSlider, QWidget]:
        """Build a 0..100 slider plus 'auto' checkbox for a hardware property.

        The slider value is normalised to 0..1 when emitted/saved so
        platforms can map to whatever range OpenCV expects.
        """
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setToolTip(
            f"{label} of the camera. Move to taste; tick 'auto' to leave the "
            "camera at its default."
        )
        slider.setEnabled(value is not None)
        if value is not None:
            slider.setValue(round(value * 100))
        row.addWidget(slider, 1)

        auto = QCheckBox("auto")
        auto.setChecked(value is None)
        auto.setToolTip(
            "When ticked, the camera's own default is used and ShotTrainer "
            "will not override it."
        )
        row.addWidget(auto)

        def _on_auto(checked: bool) -> None:
            slider.setEnabled(not checked)
            self.camera_property_changed.emit(
                name, None if checked else slider.value() / 100.0
            )

        def _on_slider(v: int) -> None:
            if not auto.isChecked():
                self.camera_property_changed.emit(name, v / 100.0)

        auto.toggled.connect(_on_auto)
        slider.valueChanged.connect(_on_slider)

        # Stash on the slider so _on_save can read the auto state.
        slider.setProperty("auto_checkbox", id(auto))
        slider._auto_checkbox = auto  # type: ignore[attr-defined]

        return slider, container

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

        # Dropdown of the most common calibres. Picking a preset
        # sets the diameter spinbox. Users can still type a custom value.
        self._calibre = _make_combo(
            [
                ("custom", "Custom"),
                ("177", ".177 air pellet (4.5 mm)"),
                ("20", ".20 air pellet (5.0 mm)"),
                ("22", ".22 (5.6 mm)"),
                ("25", ".25 (6.35 mm)"),
                ("9mm", "9 mm"),
                ("45", ".45 (11.43 mm)"),
            ],
            tooltip="Common projectile calibres. Pick one or type a custom diameter below.",
            initial=self._calibre_for_diameter(prefs.shot_diameter_mm),
        )
        self._calibre.currentIndexChanged.connect(self._on_calibre_changed)
        form.addRow("Calibre", self._calibre)

        self._shot_diameter = QDoubleSpinBox()
        self._shot_diameter.setRange(0.5, 25.0)
        self._shot_diameter.setSingleStep(0.1)
        self._shot_diameter.setSuffix(" mm")
        self._shot_diameter.setValue(prefs.shot_diameter_mm)
        self._shot_diameter.setToolTip(
            "Pellet/bullet diameter. Used to draw shots at their correct size on "
            "the target view (4.5 mm for .177 air, 5.6 mm for .22)."
        )
        self._shot_diameter.valueChanged.connect(self._on_shot_diameter_changed)
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

    def _calibre_for_diameter(self, mm: float) -> str:
        for key, value in CALIBRES_MM.items():
            if abs(value - mm) < 0.05:
                return key
        return "custom"

    def _on_calibre_changed(self, _index: int) -> None:
        key = self._calibre.currentData()
        if isinstance(key, str) and key in CALIBRES_MM:
            # Block signals during the spinbox update so the change
            # doesn't flip the dropdown back to "Custom".
            self._shot_diameter.blockSignals(True)
            self._shot_diameter.setValue(CALIBRES_MM[key])
            self._shot_diameter.blockSignals(False)

    def _on_shot_diameter_changed(self, value: float) -> None:
        # Manual edit invalidates the preset selection.
        self._calibre.blockSignals(True)
        idx = self._calibre.findData(self._calibre_for_diameter(value))
        if idx >= 0:
            self._calibre.setCurrentIndex(idx)
        self._calibre.blockSignals(False)

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

        def _slider_value(slider: QSlider) -> float | None:
            auto = getattr(slider, "_auto_checkbox", None)
            if auto is not None and auto.isChecked():
                return None
            return slider.value() / 100.0

        updated = Preferences(
            camera_id=int(cam_id) if cam_id is not None else 0,
            camera_rotation=int(rotation) if rotation is not None else 0,
            camera_flip_h=self._flip_h.isChecked(),
            camera_flip_v=self._flip_v.isChecked(),
            camera_brightness=_slider_value(self._brightness),
            camera_contrast=_slider_value(self._contrast),
            camera_saturation=_slider_value(self._saturation),
            camera_gain=_slider_value(self._gain),
            camera_exposure=_slider_value(self._exposure),
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
