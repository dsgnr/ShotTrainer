"""Preferences covering device choices, sensitivity and recording windows."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


@dataclass(slots=True)
class Preferences:
    camera_id: int = 0
    audio_device: str = "default"
    shot_threshold: float = 0.25
    shot_refractory_ms: int = 400
    pre_shot_ms: int = 1500
    post_shot_ms: int = 800


class PreferencesDialog(QDialog):
    saved = Signal(Preferences)

    def __init__(
        self,
        prefs: Preferences,
        camera_options: list[tuple[int, str]] | None = None,
        audio_options: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self._prefs = prefs

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._camera = QComboBox()
        for cam_id, name in camera_options or [(0, "Camera 0")]:
            self._camera.addItem(name, cam_id)
        index = self._camera.findData(prefs.camera_id)
        if index >= 0:
            self._camera.setCurrentIndex(index)
        form.addRow("Camera", self._camera)

        self._audio = QComboBox()
        for name in audio_options or ["default"]:
            self._audio.addItem(name)
        idx = self._audio.findText(prefs.audio_device)
        if idx >= 0:
            self._audio.setCurrentIndex(idx)
        form.addRow("Microphone", self._audio)

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.01, 1.0)
        self._threshold.setSingleStep(0.01)
        self._threshold.setValue(prefs.shot_threshold)
        form.addRow("Shot threshold", self._threshold)

        self._refractory = QSpinBox()
        self._refractory.setRange(50, 5000)
        self._refractory.setSuffix(" ms")
        self._refractory.setValue(prefs.shot_refractory_ms)
        form.addRow("Refractory window", self._refractory)

        self._pre = QSpinBox()
        self._pre.setRange(0, 10000)
        self._pre.setSuffix(" ms")
        self._pre.setValue(prefs.pre_shot_ms)
        form.addRow("Pre-shot window", self._pre)

        self._post = QSpinBox()
        self._post.setRange(0, 10000)
        self._post.setSuffix(" ms")
        self._post.setValue(prefs.post_shot_ms)
        form.addRow("Post-shot window", self._post)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

    def _on_save(self) -> None:
        cam_id = self._camera.currentData()
        audio = self._audio.currentText()
        updated = Preferences(
            camera_id=int(cam_id) if cam_id is not None else 0,
            audio_device=audio,
            shot_threshold=float(self._threshold.value()),
            shot_refractory_ms=int(self._refractory.value()),
            pre_shot_ms=int(self._pre.value()),
            post_shot_ms=int(self._post.value()),
        )
        self.saved.emit(updated)
        self.accept()
