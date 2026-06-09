"""Camera lifecycle and device enumeration logic.

Extracted from the controller so camera-related concerns
(start, stop, device enumeration, popout preview) live in one
place. The controller remains the orchestrator but delegates
the details here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt

from shottrainer.tracking.camera import CameraCapture, CameraConfig, list_available_cameras

from .camera_selection import (
    CameraSelection,
    load_camera_selection,
    resolve_camera_index,
    save_camera_selection,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from shottrainer.ui.camera_popout import CameraPopout
    from shottrainer.ui.main_window import MainWindow

log = logging.getLogger(__name__)


class CameraManager:
    """Manages camera capture lifecycle, device enumeration, and the popout preview.

    Owns the running `CameraCapture` instance and the list of
    frame mirrors (dialogs receiving live frames). The controller
    feeds it preferences and connects UI signals; this class
    handles the start/stop mechanics and the popout window.
    """

    def __init__(
        self,
        window: MainWindow,
        on_frame_slot: Callable[[np.ndarray, float, int], None],
        on_camera_error_slot: Callable[[str], None],
    ) -> None:
        self._window = window
        self._on_frame_slot = on_frame_slot
        self._on_camera_error_slot = on_camera_error_slot
        self._camera: CameraCapture | None = None
        self._camera_popout: CameraPopout | None = None
        self._frame_mirrors: list = []
        self._cached_camera_options: list[tuple[int, str]] = []

    @property
    def camera(self) -> CameraCapture | None:
        """The running capture instance, or ``None`` if stopped."""
        return self._camera

    @property
    def frame_mirrors(self) -> list:
        """Dialogs currently receiving live frame and audio-level pushes."""
        return self._frame_mirrors

    @property
    def cached_camera_options(self) -> list[tuple[int, str]]:
        """Device list from the most recent enumeration."""
        return self._cached_camera_options

    def effective_camera_index(self) -> int | None:
        """Pick the camera index to use given the saved selection.

        Lists the attached devices and prefers a match by name so
        the saved camera follows the user across reboots even when
        USB devices renumber. Falls back to the saved index, then
        to ``0``. Returns ``None`` only when the user has explicitly
        chosen "no camera" and nothing is attached.

        Returns:
            The resolved device index, or ``None`` for "no camera".
        """
        selection = load_camera_selection()
        if selection.index is None and not selection.name:
            return None
        try:
            available = list_available_cameras()
        except Exception:  # pragma: no cover - driver dependent
            available = []
        if not available:
            return selection.index if selection.index is not None else None
        return resolve_camera_index(selection, available)

    def persist_camera_selection(self, index: int | None) -> None:
        """Save the camera the user just picked.

        Uses the cached enumeration from the most recent Preferences
        dialog so this path doesn't re-probe the device tree. Falls
        back to a plain ``Camera N`` label when no cache is available.

        Args:
            index: Device index to persist, or ``None`` for "no camera".
        """
        if index is None:
            try:
                save_camera_selection(CameraSelection(name="", index=None))
            except OSError as exc:
                log.warning("Could not save camera selection: %s", exc)
            return
        name = next(
            (n for i, n in self._cached_camera_options if i == index),
            f"Camera {index}",
        )
        try:
            save_camera_selection(CameraSelection(name=name, index=index))
        except OSError as exc:
            log.warning("Could not save camera selection: %s", exc)

    def start_camera(self, device_index: int) -> None:
        """Stop any running capture and bring up a fresh one.

        Always builds a new `CameraCapture` because the worker is
        single-use. Connects the frame-ready signal with a
        ``DirectConnection`` so detection runs on the worker thread.

        Args:
            device_index: The integer device index to open.
        """
        self.stop_camera()
        cam = CameraCapture(CameraConfig(device_index=device_index))
        cam.frame_ready.connect(self._on_frame_slot, type=Qt.ConnectionType.DirectConnection)
        cam.error.connect(self._on_camera_error_slot)
        cam.start()
        self._camera = cam

    def stop_camera(self) -> None:
        """Stop the worker thread and reset the camera view's status pill."""
        if self._camera is not None:
            self._camera.stop()
            self._camera = None
            self._window.camera_view.set_status("idle")

    def device_index(self) -> int | None:
        """Return the device index of the running capture, or ``None``."""
        cam = self._camera
        if cam is None:
            return None
        return cam.device_index

    def device_options(self) -> tuple[list[tuple[int, str]], list[str]]:
        """List cameras and microphones for the Preferences dialog.

        The camera list is cached so `persist_camera_selection` can
        look up a label by index later without re-probing.

        Returns:
            A tuple of (camera_list, microphone_list).
        """
        from shottrainer.audio.input import list_audio_inputs

        cameras = list_available_cameras() or [(0, "Camera 0")]
        mics = list_audio_inputs()
        self._cached_camera_options = cameras
        return cameras, mics

    def register_frame_mirror(self, dialog) -> None:
        """Forward live frames and audio levels to ``dialog`` until it closes.

        Args:
            dialog: Any object implementing the `_FrameMirror` protocol.
        """
        self._frame_mirrors.append(dialog)
        dialog.finished.connect(
            lambda _r, d=dialog: self._frame_mirrors.remove(d) if d in self._frame_mirrors else None
        )

    def open_popout(self, latest_frame: np.ndarray | None) -> None:
        """Open or raise the enlarged camera preview dialog.

        Args:
            latest_frame: The most recent greyscale frame, or ``None``.
        """
        from shottrainer.ui.camera_popout import CameraPopout

        if self._camera_popout is not None and self._camera_popout.isVisible():
            self._camera_popout.raise_()
            self._camera_popout.activateWindow()
            return

        popout = CameraPopout(self._window)
        self._camera_popout = popout

        if latest_frame is not None:
            popout.view.set_frame(latest_frame)
            popout.view.set_region_fraction(self._window.camera_view._region_fraction)
            h, w = latest_frame.shape[:2]
            popout.set_resolution(w, h)
        self._frame_mirrors.append(popout.view)
        popout.finished.connect(self._on_popout_closed)
        popout.show()
        popout.raise_()
        popout.activateWindow()

    def _on_popout_closed(self, _result: int) -> None:
        """Clean up when the popout dialog closes."""
        if self._camera_popout is not None:
            view = self._camera_popout.view
            if view in self._frame_mirrors:
                self._frame_mirrors.remove(view)
            self._camera_popout = None
