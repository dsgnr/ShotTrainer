"""The Preferences dialog with tabbed layout, live camera preview and target picker."""

from __future__ import annotations

from collections.abc import Callable

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

from shottrainer.app.preferences import Preferences
from shottrainer.app.target_faces import TargetFace, TargetRing

from .camera_view import CameraView
from .target_face_preview import TargetFacePreview

ROTATION_OPTIONS: tuple[tuple[int, str], ...] = (
    (0, "None"),
    (90, "90 clockwise"),
    (180, "180"),
    (270, "90 counter-clockwise"),
)


CALIBRES: tuple[tuple[str, str, float], ...] = (
    ("177", ".177 air pellet (4.5 mm)", 4.5),
    ("20", ".20 air pellet (5.0 mm)", 5.0),
    ("22", ".22 (5.6 mm)", 5.6),
    ("25", ".25 (6.35 mm)", 6.35),
    ("9mm", "9 mm", 9.0),
    ("45", ".45 (11.43 mm)", 11.43),
)
_CALIBRES_BY_KEY: dict[str, float] = {key: mm for key, _label, mm in CALIBRES}


def _make_combo(
    items: list[tuple[object, str]],
    *,
    initial: object | None = None,
) -> QComboBox:
    """Build a QComboBox whose popup view sizes to its longest entry."""
    combo = QComboBox()
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
    for value, label in items:
        combo.addItem(label, value)
    if initial is not None:
        idx = combo.findData(initial)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    # Make the popup wide enough to read the longest entry, regardless
    # of how narrow the dropdown itself is.
    metrics = combo.fontMetrics()
    max_w = max((metrics.horizontalAdvance(label) for _, label in items), default=120)
    combo.view().setMinimumWidth(max_w + 32)
    return combo


def _add_field_with_hint(
    form: QFormLayout,
    label_text: str,
    field: QWidget,
    hint_text: str,
) -> None:
    """Add a row with the field, then a wrapped hint as its own row.

    Putting the hint in the form layout directly (rather than
    nesting it inside the field's container) lets QFormLayout
    honour the label's wrapped ``heightForWidth``, so longer
    hints aren't clipped.
    """
    form.addRow(label_text, field)
    hint = QLabel(hint_text)
    hint.setObjectName("formHint")
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #8a8a8a;")
    hint.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
    form.addRow("", hint)


def _section_label(text: str) -> QLabel:
    """Build a small uppercase heading for grouping fields in a tab."""
    label = QLabel(text.upper())
    label.setObjectName("prefsSection")
    return label


class _PropertySlider(QWidget):
    """A horizontal slider over a float range with a Reset button.

    Used for the software image controls (brightness, contrast).
    The slider's integer position is mapped to the configured
    float range. ``value()`` returns the current float. The
    Reset button snaps back to ``default`` and fires the change
    so the live preview updates.
    """

    value_changed = Signal(str, object)  # property name, float

    def __init__(
        self,
        name: str,
        initial: float,
        *,
        minimum: float,
        maximum: float,
        default: float,
        steps: int = 200,
        suffix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._minimum = minimum
        self._maximum = maximum
        self._default = default
        self._steps = steps
        self._suffix = suffix

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, steps)
        self._slider.setValue(self._float_to_pos(initial))
        layout.addWidget(self._slider, 1)

        self._readout = QLabel()
        self._readout.setMinimumWidth(56)
        self._readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._readout)

        self._reset = QPushButton("Reset")
        self._reset.setToolTip("Restore the default value")
        layout.addWidget(self._reset)

        self._slider.valueChanged.connect(self._on_slider_changed)
        self._reset.clicked.connect(self._on_reset_clicked)
        self._update_readout()

    def value(self) -> float:
        """Return the current slider value as a float."""
        return self._pos_to_float(self._slider.value())

    def set_value(self, value: float) -> None:
        """Move the slider to ``value`` without firing ``value_changed``.

        Used when the controller wants to push a programmatic
        value into the widget (after auto-optimise, for example)
        without it looking like the user dragged the slider.
        """
        self._slider.blockSignals(True)
        try:
            self._slider.setValue(self._float_to_pos(value))
        finally:
            self._slider.blockSignals(False)
        self._update_readout()

    def _pos_to_float(self, pos: int) -> float:
        ratio = pos / self._steps
        return self._minimum + ratio * (self._maximum - self._minimum)

    def _float_to_pos(self, value: float) -> int:
        clamped = max(self._minimum, min(self._maximum, value))
        ratio = (clamped - self._minimum) / (self._maximum - self._minimum)
        return round(ratio * self._steps)

    def _update_readout(self) -> None:
        value = self.value()
        if self._suffix:
            self._readout.setText(f"{value:.2f}")
        else:
            self._readout.setText(f"{value:+.0f}")

    def _on_slider_changed(self, _value: int) -> None:
        self._update_readout()
        self.value_changed.emit(self._name, self.value())

    def _on_reset_clicked(self) -> None:
        self._slider.setValue(self._float_to_pos(self._default))


class PreferencesDialog(QDialog):
    saved = Signal(Preferences)
    optimise_requested = Signal()
    reset_detector_requested = Signal()
    camera_property_changed = Signal(str, object)
    camera_transform_changed = Signal(int, bool, bool)  # rotation_deg, flip_h, flip_v
    # Emitted as soon as the user picks a different camera in the
    # dropdown. Carries the new index, or ``None`` for "no camera". The
    # controller uses this to swap the live capture immediately so
    # the embedded preview reflects the new device without waiting
    # for Save.
    camera_changed = Signal(object)
    # Emitted when the user clicks the "Refresh" button next to the
    # camera dropdown. The controller responds by re-enumerating the
    # device list and calling :meth:`set_camera_options` /
    # :meth:`set_audio_options`.
    refresh_devices_requested = Signal()

    def __init__(
        self,
        prefs: Preferences,
        camera_options: list[tuple[int, str]] | None = None,
        audio_options: list[str] | None = None,
        target_faces: list[tuple[str, str]] | None = None,
        rings_lookup: Callable[[str], tuple[TargetRing, ...]] | None = None,
        face_lookup: Callable[[str], TargetFace | None] | None = None,
        saved_camera_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(720, 560)
        self._prefs = prefs
        self._rings_lookup = rings_lookup
        self._face_lookup = face_lookup
        self._saved_camera_name = saved_camera_name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
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

        The frame has already been through the capture pipeline,
        so the rotation, flip and image-control choices are
        already applied. The dialog only has to display it.
        """
        self._latest_raw_frame = frame_bgr
        self._refresh_preview_frame()

    def _refresh_preview_frame(self) -> None:
        """Repaint the embedded camera preview with the latest frame."""
        frame = getattr(self, "_latest_raw_frame", None)
        if frame is None:
            return
        self._camera_preview.set_frame(frame)
        self._camera_preview.set_region_fraction(float(self._region.value()))

    def _on_region_preview_changed(self, _value: float) -> None:
        self._camera_preview.set_region_fraction(float(self._region.value()))

    def _emit_transform_changed(self) -> None:
        """Tell the controller about a rotation or flip change.

        The controller updates the live capture pipeline so the
        preview reflects the new orientation immediately. The
        change is only saved when the user clicks Save. The
        cancel path restores the previous transform via
        :meth:`AppController._apply_preferences`.
        """
        rotation = int(self._rotation.currentData() or 0)
        self.camera_transform_changed.emit(
            rotation,
            self._flip_h.isChecked(),
            self._flip_v.isChecked(),
        )

    def push_audio_level(self, level: float) -> None:
        """Update the audio level meter (input is 0..1)."""
        v = round(min(1.0, max(0.0, level)) * 100)
        self._audio_meter.setValue(v)

    def set_detector_status(self, text: str, *, kind: str = "info") -> None:
        """Show a one-line result next to the auto-optimise button.

        ``kind`` is ``"info"`` for neutral messages, ``"success"`` for
        a useful result and ``"warning"`` when nothing changed.
        """
        colours = {
            "info": "#8a8a8a",
            "success": "#27ae60",
            "warning": "#e67e22",
        }
        colour = colours.get(kind, colours["info"])
        self._detector_status.setStyleSheet(f"color: {colour};")
        self._detector_status.setText(text)

    def set_image_controls(self, brightness: float, contrast: float) -> None:
        """Snap the brightness and contrast sliders to the given values.

        Used by the controller when the auto-optimiser settles
        on a different adjustment, so the user can see what the
        button picked. The sliders' ``set_value`` doesn't fire
        ``camera_property_changed``, so the change doesn't feed
        back into the controller as if the user had dragged the
        slider themselves.
        """
        self._brightness.set_value(brightness)
        self._contrast.set_value(contrast)

    def set_optimise_enabled(self, enabled: bool) -> None:
        """Enable or disable the Auto-optimise button.

        Disabled while the optimiser is running on its worker
        thread so the user can't queue a second click.
        Re-enabled when the result lands.
        """
        self._optimise_btn.setEnabled(enabled)
        self._optimise_btn.setText(
            "Auto-optimise tracking" if enabled else "Optimising..."
        )

    def set_camera_options(self, options: list[tuple[int, str]]) -> None:
        """Rebuild the camera dropdown from a fresh enumeration.

        Keeps the selection by the *displayed name*, not by
        index. Plugging in a new device can shift the indices.
        What used to be index 0 (the built-in FaceTime HD)
        becomes index 1 when a USB camera comes in at index 0.
        Matching by name keeps the user on the same physical
        device after a refresh. If the device they had selected
        is gone, the dropdown falls back to "No camera".

        Sends out :attr:`camera_changed` when the integer index
        attached to the user's selected device has shifted, so
        the controller can restart the live preview on the new
        index. Without this the preview would silently end up
        showing whichever physical device sat at the old index.
        """
        previous_name = self._camera.currentText()
        previous_index = self._camera.currentData()
        items: list[tuple[object, str]] = list(options or [(0, "Camera 0")])
        names = {label for _, label in items}
        if previous_name in names:
            new_initial: object = next(idx for idx, label in items if label == previous_name)
        else:
            items.insert(0, (None, "No camera"))
            new_initial = None
        self._camera.blockSignals(True)
        try:
            self._camera.clear()
            for value, label in items:
                self._camera.addItem(label, value)
            target = self._camera.findData(new_initial)
            if target >= 0:
                self._camera.setCurrentIndex(target)
        finally:
            self._camera.blockSignals(False)
        if new_initial != previous_index:
            self.camera_changed.emit(
                new_initial if isinstance(new_initial, int) else None
            )

    def set_audio_options(self, options: list[str]) -> None:
        """Rebuild the audio-input dropdown with a fresh device list."""
        previous = self._audio.currentText()
        names = list(options or ["default"])
        self._audio.blockSignals(True)
        try:
            self._audio.clear()
            for name in names:
                self._audio.addItem(name, name)
            target = self._audio.findText(previous)
            if target >= 0:
                self._audio.setCurrentIndex(target)
        finally:
            self._audio.blockSignals(False)

    def selected_camera_index(self) -> int | None:
        """The integer index currently selected in the dropdown, or ``None``.

        ``None`` for the "No camera" entry. The controller uses
        this to keep the live capture in sync with whatever the
        dialog has chosen.
        """
        value = self._camera.currentData()
        return value if isinstance(value, int) else None

    def _build_camera_tab(
        self,
        prefs: Preferences,
        camera_options: list[tuple[int, str]] | None,
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Device section.
        layout.addWidget(_section_label("Device"))
        device_form = QFormLayout()
        device_form.setHorizontalSpacing(16)
        device_form.setVerticalSpacing(12)
        cam_items: list[tuple[object, str]] = list(camera_options or [(0, "Camera 0")])
        # Pick the saved camera by *name* first, falling back to the
        # saved index. Names are stable across reboots and across
        # newly-attached devices that shift the integer indices.
        # Indices alone are not. If neither matches, prepend a "No
        # camera" entry so the user has to make an explicit choice.
        names = {label: idx for idx, label in cam_items if isinstance(idx, int)}
        saved_indices = set(names.values())
        initial_camera: object
        if self._saved_camera_name and self._saved_camera_name in names:
            initial_camera = names[self._saved_camera_name]
        elif prefs.camera_id is not None and prefs.camera_id in saved_indices:
            initial_camera = prefs.camera_id
        else:
            cam_items.insert(0, (None, "No camera"))
            initial_camera = None
        self._camera = _make_combo(cam_items, initial=initial_camera)
        self._camera.activated.connect(self._on_camera_chosen)

        # Refresh button next to the dropdown so a camera plugged in
        # after launch can be picked up without restarting the app.
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setToolTip(
            "Re-enumerate attached cameras and microphones. Use this "
            "after plugging in a new camera."
        )
        refresh_btn.clicked.connect(self.refresh_devices_requested)
        device_row = QWidget()
        device_layout = QHBoxLayout(device_row)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.setSpacing(8)
        device_layout.addWidget(self._camera, 1)
        device_layout.addWidget(refresh_btn)
        device_form.addRow("Device", device_row)

        self._rotation = _make_combo(list(ROTATION_OPTIONS), initial=prefs.camera_rotation)
        self._rotation.currentIndexChanged.connect(lambda _i: self._emit_transform_changed())
        device_form.addRow("Rotation", self._rotation)

        flip_row = QWidget()
        flip_layout = QHBoxLayout(flip_row)
        flip_layout.setContentsMargins(0, 0, 0, 0)
        flip_layout.setSpacing(12)
        self._flip_h = QCheckBox("Mirror horizontally")
        self._flip_h.setChecked(prefs.camera_flip_h)
        self._flip_h.toggled.connect(lambda _v: self._emit_transform_changed())
        flip_layout.addWidget(self._flip_h)

        self._flip_v = QCheckBox("Mirror vertically")
        self._flip_v.setChecked(prefs.camera_flip_v)
        self._flip_v.toggled.connect(lambda _v: self._emit_transform_changed())
        flip_layout.addWidget(self._flip_v)
        flip_layout.addStretch(1)
        device_form.addRow("Mirror", flip_row)

        # Trace direction. Independent of the camera image flips above:
        # "Mirror" changes how the live frame is shown and tracked,
        # whereas "Invert trace" changes how the tracked position is
        # converted into target millimetres. Useful when an optical
        # element (a magnifying scope, a mirror) puts the image-vs-aim
        # relationship the wrong way round for the default sign flip.
        invert_row = QWidget()
        invert_layout = QHBoxLayout(invert_row)
        invert_layout.setContentsMargins(0, 0, 0, 0)
        invert_layout.setSpacing(12)
        self._invert_h = QCheckBox("Invert horizontal")
        self._invert_h.setChecked(prefs.invert_trace_horizontal)
        invert_layout.addWidget(self._invert_h)
        self._invert_v = QCheckBox("Invert vertical")
        self._invert_v.setChecked(prefs.invert_trace_vertical)
        invert_layout.addWidget(self._invert_v)
        invert_layout.addStretch(1)
        device_form.addRow("Invert trace", invert_row)
        layout.addLayout(device_form)

        # Tracking section.
        layout.addWidget(_section_label("Tracking"))
        tracking_form = QFormLayout()
        tracking_form.setHorizontalSpacing(16)
        tracking_form.setVerticalSpacing(12)

        self._region = QDoubleSpinBox()
        self._region.setRange(0.1, 1.0)
        self._region.setSingleStep(0.05)
        self._region.setDecimals(2)
        self._region.setValue(prefs.tracking_region_fraction)
        self._region.valueChanged.connect(self._on_region_preview_changed)
        _add_field_with_hint(
            tracking_form,
            "Tracking region",
            self._region,
            "Fraction of the frame the detector searches in. Lower it "
            "if the camera picks up dark objects near the edges.",
        )
        layout.addLayout(tracking_form)

        # Image section.
        layout.addWidget(_section_label("Image"))
        image_form = QFormLayout()
        image_form.setHorizontalSpacing(16)
        image_form.setVerticalSpacing(12)

        # Software image controls. Each slider has a Reset button to
        # snap back to the default ("no change") value.
        self._brightness = self._make_property_slider(
            "brightness",
            prefs.camera_brightness,
            minimum=-100.0,
            maximum=100.0,
            default=0.0,
        )
        image_form.addRow("Brightness", self._brightness)
        self._contrast = self._make_property_slider(
            "contrast",
            prefs.camera_contrast,
            minimum=0.5,
            maximum=2.0,
            default=1.0,
            suffix="x",
        )
        image_form.addRow("Contrast", self._contrast)

        layout.addLayout(image_form)

        self._optimise_btn = QPushButton("Auto-optimise tracking")
        self._optimise_btn.clicked.connect(self.optimise_requested)

        self._reset_detector_btn = QPushButton("Reset")
        self._reset_detector_btn.clicked.connect(self.reset_detector_requested)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addWidget(self._optimise_btn, 1)
        button_row.addWidget(self._reset_detector_btn)
        layout.addLayout(button_row)

        # Inline status line for the auto-optimise / reset buttons. Kept
        # in the dialog rather than the main window's status bar so the
        # user can see the result without having to close the dialog.
        self._detector_status = QLabel("")
        self._detector_status.setObjectName("detectorStatus")
        self._detector_status.setWordWrap(True)
        self._detector_status.setStyleSheet("color: #8a8a8a;")
        layout.addWidget(self._detector_status)

        self._camera_preview = CameraView()
        self._camera_preview.setMinimumHeight(160)
        self._camera_preview.set_region_fraction(prefs.tracking_region_fraction)
        layout.addWidget(self._camera_preview, 1)

        return page

    def _make_property_slider(
        self,
        name: str,
        value: float,
        *,
        minimum: float,
        maximum: float,
        default: float,
        suffix: str = "",
    ) -> _PropertySlider:
        """Build a property slider and forward its changes to the controller."""
        slider = _PropertySlider(
            name,
            value,
            minimum=minimum,
            maximum=maximum,
            default=default,
            suffix=suffix,
        )
        slider.value_changed.connect(self.camera_property_changed)
        return slider

    def _build_audio_tab(
        self,
        prefs: Preferences,
        audio_options: list[str] | None,
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Input section.
        layout.addWidget(_section_label("Input"))
        input_form = QFormLayout()
        input_form.setHorizontalSpacing(16)
        input_form.setVerticalSpacing(12)

        audio_items = [(name, name) for name in (audio_options or ["default"])]
        self._audio = _make_combo(audio_items, initial=prefs.audio_device)
        input_form.addRow("Input", self._audio)

        self._audio_gain = QDoubleSpinBox()
        self._audio_gain.setRange(0.1, 10.0)
        self._audio_gain.setSingleStep(0.1)
        self._audio_gain.setSuffix("x")
        self._audio_gain.setValue(prefs.audio_gain)
        _add_field_with_hint(
            input_form,
            "Volume",
            self._audio_gain,
            "Software gain on the mic input. Raise if quiet shots don't "
            "register. Lower if loud noises cause false triggers.",
        )
        layout.addLayout(input_form)

        # Detection section.
        layout.addWidget(_section_label("Detection"))
        detection_form = QFormLayout()
        detection_form.setHorizontalSpacing(16)
        detection_form.setVerticalSpacing(12)

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.01, 1.0)
        self._threshold.setSingleStep(0.01)
        self._threshold.setValue(prefs.shot_threshold)
        _add_field_with_hint(
            detection_form,
            "Shot threshold",
            self._threshold,
            "Audio level above which a shot is registered (0..1). "
            "Pick a value just above the ambient noise on the live meter.",
        )

        self._refractory = QSpinBox()
        self._refractory.setRange(50, 5000)
        self._refractory.setSuffix(" ms")
        self._refractory.setValue(prefs.shot_refractory_ms)
        _add_field_with_hint(
            detection_form,
            "Refractory window",
            self._refractory,
            "Time after a shot in which further triggers are ignored. "
            "Stops echoes and ringing being counted as extra shots.",
        )
        layout.addLayout(detection_form)

        meter_row = QHBoxLayout()
        meter_row.addWidget(QLabel("Live level"))
        self._audio_meter = QProgressBar()
        self._audio_meter.setRange(0, 100)
        self._audio_meter.setTextVisible(False)
        meter_row.addWidget(self._audio_meter, 1)
        layout.addLayout(meter_row)
        layout.addStretch(1)
        return page

    def _build_target_tab(
        self,
        prefs: Preferences,
        target_faces: list[tuple[str, str]] | None,
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Face section.
        layout.addWidget(_section_label("Face"))
        face_form = QFormLayout()
        face_form.setHorizontalSpacing(16)
        face_form.setVerticalSpacing(12)

        face_items = list(target_faces or [("default", "Default rings")])
        self._target_face = _make_combo(face_items, initial=prefs.target_face)
        face_form.addRow("Face", self._target_face)
        # Dropdown of the most common calibres. Picking a preset
        # sets the diameter spinbox. Users can still type a custom value.
        calibre_items: list[tuple[object, str]] = [("custom", "Custom")]
        calibre_items.extend((key, label) for key, label, _mm in CALIBRES)
        self._calibre = _make_combo(
            calibre_items,
            initial=self._calibre_for_diameter(prefs.shot_diameter_mm),
        )
        self._calibre.currentIndexChanged.connect(self._on_calibre_changed)
        face_form.addRow("Calibre", self._calibre)

        self._shot_diameter = QDoubleSpinBox()
        self._shot_diameter.setRange(0.5, 25.0)
        self._shot_diameter.setSingleStep(0.1)
        self._shot_diameter.setSuffix(" mm")
        self._shot_diameter.setValue(prefs.shot_diameter_mm)
        self._shot_diameter.valueChanged.connect(self._on_shot_diameter_changed)
        face_form.addRow("Shot diameter", self._shot_diameter)
        layout.addLayout(face_form)

        # Tracking section.
        layout.addWidget(_section_label("Tracking"))
        tracking_form = QFormLayout()
        tracking_form.setHorizontalSpacing(16)
        tracking_form.setVerticalSpacing(12)

        # Diameter of the printed black circle the live tracker
        # measures against. Picking the right number is the only
        # spatial parameter the user has to set. The conversion from
        # pixels to millimetres is re-derived on every frame from the
        # detected radius and this diameter.
        self._circle_diameter = QDoubleSpinBox()
        self._circle_diameter.setRange(5.0, 1000.0)
        self._circle_diameter.setSingleStep(1.0)
        self._circle_diameter.setSuffix(" mm")
        self._circle_diameter.setValue(prefs.circle_diameter_mm)
        _add_field_with_hint(
            tracking_form,
            "Tracking circle",
            self._circle_diameter,
            "Diameter of the printed black circle the live tracker "
            "uses for scale. Set this to the size of the aiming mark "
            "you're shooting at.",
        )
        layout.addLayout(tracking_form)

        self._face_preview = TargetFacePreview()
        layout.addWidget(self._face_preview, 1)
        self._target_face.currentIndexChanged.connect(self._refresh_face_preview)
        # Populate the calibre and tracking-circle spinboxes from the
        # face's metadata when the *user* changes the face. Connect
        # this only after the spinboxes exist and after the dialog
        # has been initialised with the saved preferences, so opening
        # the dialog never overwrites what the user previously saved.
        self._target_face.activated.connect(self._on_face_chosen)
        self._refresh_face_preview()

        return page

    def _on_face_chosen(self, _index: int) -> None:
        """Auto-fill the diameter fields from the chosen face.

        Only runs on a deliberate user pick from the ``activated``
        signal, not on the programmatic ``setCurrentIndex`` call
        during dialog construction. Missing metadata is left alone,
        so any values the user already set stay put.
        """
        if self._face_lookup is None:
            return
        key = self._target_face.currentData()
        if not isinstance(key, str):
            return
        face = self._face_lookup(key)
        if face is None:
            return
        if face.shot_diameter_mm is not None:
            self._shot_diameter.setValue(face.shot_diameter_mm)
        if face.face_diameter_mm is not None:
            self._circle_diameter.setValue(face.face_diameter_mm)

    def _refresh_face_preview(self) -> None:
        if self._rings_lookup is None:
            return
        key = self._target_face.currentData()
        if not isinstance(key, str):
            return
        rings = self._rings_lookup(key)
        self._face_preview.set_rings(rings)

    def _on_camera_chosen(self, _index: int) -> None:
        """Tell the controller as soon as the user picks a different camera.

        Only runs on a deliberate user pick from the ``activated``
        signal, so opening the dialog with the saved camera
        preselected doesn't trigger a needless capture restart.
        ``None`` passes through as the new camera id, meaning
        "stop the live capture".
        """
        new_id = self._camera.currentData()
        self.camera_changed.emit(new_id if isinstance(new_id, int) else None)
        # The image controls are reapplied to the new device on
        # the next capture cycle by the controller. The slider values
        # themselves stay where the user had them.

    def _calibre_for_diameter(self, mm: float) -> str:
        """Return the preset key whose diameter matches ``mm`` (or "custom")."""
        for key, value in _CALIBRES_BY_KEY.items():
            if abs(value - mm) < 0.05:
                return key
        return "custom"

    def _on_calibre_changed(self, _index: int) -> None:
        key = self._calibre.currentData()
        if isinstance(key, str) and key in _CALIBRES_BY_KEY:
            # Block signals during the spinbox update so the change
            # doesn't flip the dropdown back to "Custom".
            self._shot_diameter.blockSignals(True)
            self._shot_diameter.setValue(_CALIBRES_BY_KEY[key])
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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        layout.addWidget(_section_label("Replay window"))
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        self._pre = QSpinBox()
        self._pre.setRange(0, 10000)
        self._pre.setSuffix(" ms")
        self._pre.setValue(prefs.pre_shot_ms)
        _add_field_with_hint(
            form,
            "Pre-shot window",
            self._pre,
            "Trace kept before each shot, used for hold-stability and "
            "tremor analysis on replay.",
        )

        self._post = QSpinBox()
        self._post.setRange(0, 10000)
        self._post.setSuffix(" ms")
        self._post.setValue(prefs.post_shot_ms)
        _add_field_with_hint(
            form,
            "Post-shot window",
            self._post,
            "Trace kept after each shot for follow-through review.",
        )
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_about_tab(self) -> QWidget:
        from shottrainer import __version__
        from shottrainer.ui.assets import asset_path

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        from PySide6.QtGui import QPixmap

        logo_label = QLabel()
        pixmap = QPixmap(str(asset_path("icon_128.png")))
        if not pixmap.isNull():
            logo_label.setPixmap(
                pixmap.scaled(
                    96,
                    96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("ShotTrainer")
        title.setObjectName("aboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)

        meta = QLabel(
            f"Version {__version__}  ·  GPL-3.0-or-later"
        )
        meta.setObjectName("aboutMeta")
        meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(meta, 0, Qt.AlignmentFlag.AlignHCenter)

        links = QLabel(
            '<a href="https://github.com/dsgnr/ShotTrainer/blob/main/README.md">README</a>'
            ' &middot; '
            '<a href="https://github.com/dsgnr/ShotTrainer">GitHub</a>'
        )
        links.setTextFormat(Qt.TextFormat.RichText)
        links.setOpenExternalLinks(True)
        links.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(links)
        layout.addStretch(1)
        return page

    def _on_save(self) -> None:
        """Build a :class:`Preferences` from the dialog state, emit it and accept.

        Reads every widget back to its saved value. Dropdown
        ``currentData`` for the camera, audio device and target
        face, slider values for the image properties, and so on.
        """
        cam_id = self._camera.currentData()
        rotation = self._rotation.currentData()
        audio = self._audio.currentText()
        target_face = self._target_face.currentData() or "default"

        updated = Preferences(
            camera_id=int(cam_id) if isinstance(cam_id, int) else None,
            camera_rotation=int(rotation) if rotation is not None else 0,
            camera_flip_h=self._flip_h.isChecked(),
            camera_flip_v=self._flip_v.isChecked(),
            camera_brightness=float(self._brightness.value()),
            camera_contrast=float(self._contrast.value()),
            audio_device=audio,
            audio_gain=float(self._audio_gain.value()),
            shot_threshold=float(self._threshold.value()),
            shot_refractory_ms=int(self._refractory.value()),
            pre_shot_ms=int(self._pre.value()),
            post_shot_ms=int(self._post.value()),
            target_face=str(target_face),
            shot_diameter_mm=float(self._shot_diameter.value()),
            tracking_region_fraction=float(self._region.value()),
            circle_diameter_mm=float(self._circle_diameter.value()),
            invert_trace_horizontal=self._invert_h.isChecked(),
            invert_trace_vertical=self._invert_v.isChecked(),
        )
        self.saved.emit(updated)
        self.accept()
