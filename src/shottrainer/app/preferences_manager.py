"""Preferences-dialog interaction logic.

Extracted from the controller so the dialog-opening, live-preview
synchronisation, auto-optimise flow, and cancel-revert paths live
together. The controller delegates here when the Preferences
dialog is involved.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from shottrainer.tracking.detector import DetectorSettings
from shottrainer.tracking.detector_tuning import ImageAdjustment, optimise_detector_settings

from .detector_store import clear_detector_settings, save_detector_settings
from .preferences import Preferences

if TYPE_CHECKING:
    import numpy as np

    from shottrainer.tracking.tracker import Tracker
    from shottrainer.ui.main_window import MainWindow

    from .camera_manager import CameraManager
    from .capture_pipeline import FrameTransformOptions

log = logging.getLogger(__name__)


class PreferencesManager:
    """Handles the Preferences dialog's live-preview and save/cancel lifecycle.

    Manages auto-optimise, detector reset, image-control slider
    synchronisation, and the revert-on-cancel logic for camera and
    transform changes.
    """

    def __init__(
        self,
        window: MainWindow,
        tracker: Tracker,
        camera_mgr: CameraManager,
        get_preferences: Callable[[], Preferences],
        set_preferences: Callable[[Preferences], None],
        set_frame_transform: Callable[[FrameTransformOptions], None],
        build_transform: Callable[[Preferences], FrameTransformOptions],
    ) -> None:
        self._window = window
        self._tracker = tracker
        self._camera_mgr = camera_mgr
        self._get_preferences = get_preferences
        self._set_preferences = set_preferences
        self._set_frame_transform = set_frame_transform
        self._build_transform = build_transform
        self._active_dialog = None
        self._latest_unadjusted_frame: np.ndarray | None = None

    @property
    def active_dialog(self):
        """The currently open Preferences dialog, or ``None``."""
        return self._active_dialog

    def set_unadjusted_frame(self, frame: np.ndarray | None) -> None:
        """Update the pre-adjustment frame snapshot for the auto-tuner.

        Args:
            frame: The latest greyscale frame before brightness/contrast.
        """
        self._latest_unadjusted_frame = frame

    def on_dialog_opened(self, dialog, latest_frame) -> None:
        """Hook the controller into a freshly opened Preferences dialog.

        Adds the dialog as a frame mirror, connects signals, and
        sets up the cancel-revert path.

        Args:
            dialog: The `PreferencesDialog` instance.
            latest_frame: The most recent frame for initial preview.
        """
        self._camera_mgr.register_frame_mirror(dialog)
        self._active_dialog = dialog
        dialog.finished.connect(self._on_dialog_closed)
        if latest_frame is not None:
            dialog.push_frame(latest_frame)
        dialog.camera_property_changed.connect(self._on_camera_property_changed)
        dialog.camera_transform_changed.connect(self._on_camera_transform_changed)
        dialog.camera_changed.connect(self._on_camera_chosen_in_dialog)
        dialog.refresh_devices_requested.connect(lambda: self._refresh_dialog_devices(dialog))
        dialog.optimise_requested.connect(self._on_optimise_requested)
        dialog.reset_detector_requested.connect(self._on_reset_detector_requested)

        original_index = self._get_preferences().camera_id
        original_prefs = self._get_preferences()
        saved = {"committed": False}

        dialog.saved.connect(lambda _prefs: saved.__setitem__("committed", True))
        dialog.finished.connect(
            lambda _r: self._revert_camera_after_dialog(original_index, saved["committed"])
        )
        dialog.finished.connect(
            lambda _r: self._revert_transform_after_dialog(original_prefs, saved["committed"])
        )

        dialog_index = dialog.selected_camera_index()
        if dialog_index != self._camera_mgr.device_index():
            if dialog_index is None:
                self._camera_mgr.stop_camera()
            else:
                self._camera_mgr.start_camera(dialog_index)

    def _on_dialog_closed(self, _result: int) -> None:
        """Drop the dialog reference once it closes."""
        self._active_dialog = None

    def _refresh_dialog_devices(self, dialog) -> None:
        """Re-enumerate cameras and microphones for the open dialog."""
        cameras, mics = self._camera_mgr.device_options()
        dialog.set_camera_options(cameras)
        dialog.set_audio_options(mics)

    def _revert_camera_after_dialog(
        self,
        original_index: int | None,
        committed: bool,
    ) -> None:
        """Undo any camera change if the dialog wasn't saved.

        Args:
            original_index: Camera index before the dialog opened.
            committed: Whether the user clicked Save.
        """
        if committed:
            return
        current_index = self._camera_mgr.device_index()
        if current_index == original_index:
            return
        if original_index is None:
            self._camera_mgr.stop_camera()
        else:
            self._camera_mgr.start_camera(original_index)

    def _revert_transform_after_dialog(
        self,
        original_prefs: Preferences,
        committed: bool,
    ) -> None:
        """Undo unsaved rotation, flip and image-control changes on cancel.

        Args:
            original_prefs: The preferences snapshot from before the dialog.
            committed: Whether the user clicked Save.
        """
        if committed:
            return
        self._set_preferences(original_prefs)
        self._set_frame_transform(self._build_transform(original_prefs))

    def _on_camera_chosen_in_dialog(self, new_index: int | None) -> None:
        """Swap the live capture so the preview shows the chosen camera."""
        if new_index is None:
            self._camera_mgr.stop_camera()
            self._window.set_tracking_status("No camera selected")
            return
        try:
            index = int(new_index)
        except (TypeError, ValueError):
            return
        self._camera_mgr.start_camera(index)

    def _on_camera_property_changed(self, name: str, value: float | None) -> None:
        """Push a brightness/contrast slider change into the live transform.

        Args:
            name: Either ``"brightness"`` or ``"contrast"``.
            value: The new numeric value from the slider.
        """
        if value is None:
            return
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return
        prefs = self._get_preferences()
        if name == "brightness":
            prefs = replace(prefs, camera_brightness=numeric)
        elif name == "contrast":
            prefs = replace(prefs, camera_contrast=numeric)
        else:
            return
        self._set_preferences(prefs)
        self._set_frame_transform(self._build_transform(prefs))

    def _on_camera_transform_changed(self, rotation: int, flip_h: bool, flip_v: bool) -> None:
        """Apply a rotation or flip change from the open dialog.

        Args:
            rotation: Clockwise rotation in degrees (0, 90, 180, 270).
            flip_h: Whether to flip horizontally.
            flip_v: Whether to flip vertically.
        """
        prefs = replace(
            self._get_preferences(),
            camera_rotation=rotation,
            camera_flip_h=flip_h,
            camera_flip_v=flip_v,
        )
        self._set_preferences(prefs)
        self._set_frame_transform(self._build_transform(prefs))

    def _on_optimise_requested(self) -> None:
        """Run the auto-tuner against the latest unadjusted frame.

        The grid search is small enough to run inline without
        a noticeable freeze (~100 ms on a typical frame).
        """
        source = self._latest_unadjusted_frame
        if source is None:
            self._set_detector_status("No camera frame available to optimise from", kind="warning")
            return

        self._set_optimise_button_enabled(False)
        self._set_detector_status("Optimising tracking...", kind="info")
        QApplication.processEvents()

        base_settings = self._tracker.detector.settings
        try:
            new_settings, adjustment, score = optimise_detector_settings(source, base_settings)
        except Exception:
            log.exception("Auto-optimise failed")
            new_settings, adjustment, score = None, None, 0.0

        self._on_optimise_finished(new_settings, adjustment, score)

    def _on_optimise_finished(
        self,
        new_settings: DetectorSettings | None,
        adjustment: ImageAdjustment | None,
        score: float,
    ) -> None:
        """Apply the optimiser's result and refresh the dialog."""
        self._set_optimise_button_enabled(True)
        if new_settings is None or adjustment is None:
            self._set_detector_status(
                "Could not find a stable target in the current frame", kind="warning"
            )
            return
        previous_settings = self._tracker.detector.settings
        previous_brightness = self._get_preferences().camera_brightness
        previous_contrast = self._get_preferences().camera_contrast
        unchanged = (
            new_settings == previous_settings
            and adjustment.brightness == previous_brightness
            and adjustment.contrast == previous_contrast
        )
        self._tracker.detector.settings = new_settings
        try:
            save_detector_settings(new_settings)
        except OSError as exc:
            log.warning("Could not save detector settings: %s", exc)
        prefs = replace(
            self._get_preferences(),
            camera_brightness=adjustment.brightness,
            camera_contrast=adjustment.contrast,
        )
        self._set_preferences(prefs)
        self._set_frame_transform(self._build_transform(prefs))
        dialog = self._active_dialog
        if dialog is not None:
            dialog.set_image_controls(adjustment.brightness, adjustment.contrast)
        if unchanged:
            self._set_detector_status(f"Already optimal (confidence {score:.2f})", kind="info")
        else:
            self._set_detector_status(
                f"Tracking optimised (confidence {score:.2f})", kind="success"
            )

    def _set_optimise_button_enabled(self, enabled: bool) -> None:
        """Enable or disable the Auto-optimise button on the open dialog."""
        dialog = self._active_dialog
        if dialog is not None:
            dialog.set_optimise_enabled(enabled)

    def _on_reset_detector_requested(self) -> None:
        """Reset the detector to defaults and delete the saved file."""
        defaults = DetectorSettings(
            region_fraction=self._get_preferences().tracking_region_fraction
        )
        self._tracker.detector.settings = defaults
        clear_detector_settings()
        self._set_detector_status("Detector reset to defaults", kind="info")

    def _set_detector_status(self, text: str, *, kind: str) -> None:
        """Show a detector status message in the status bar and dialog.

        Args:
            text: The message to display.
            kind: One of ``"info"``, ``"warning"``, ``"success"``.
        """
        timeout = 4000 if kind != "info" else 3000
        self._window.statusBar().showMessage(text, timeout)
        dialog = self._active_dialog
        if dialog is not None:
            dialog.set_detector_status(text, kind=kind)
