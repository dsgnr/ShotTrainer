"""Camera capture, run on its own Qt thread.

The capture loop sits on a worker thread so the UI never has to
wait for a frame to arrive. Each frame goes out on a Qt signal
together with a monotonic timestamp, which is the same clock the
audio detector and the recorder use, so everything ends up on a
single timeline.

The loop deliberately does nothing else. Detection, recording and
all the other domain work happen elsewhere, hooked into the
``frame_ready`` signal.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

log = logging.getLogger(__name__)


@dataclass(slots=True)
class CameraConfig:
    device_index: int = 0
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    backend: int = cv2.CAP_ANY
    # Optional hardware-side image controls. None means leave the device
    # default. Ranges depend on the camera. OpenCV typically maps them
    # to 0..1 on macOS and 0..255 on Linux/Windows, so the UI exposes a
    # normalised 0..1 slider.
    brightness: float | None = None
    contrast: float | None = None
    saturation: float | None = None
    gain: float | None = None
    exposure: float | None = None


_PROPERTIES = {
    "brightness": cv2.CAP_PROP_BRIGHTNESS,
    "contrast": cv2.CAP_PROP_CONTRAST,
    "saturation": cv2.CAP_PROP_SATURATION,
    "gain": cv2.CAP_PROP_GAIN,
    "exposure": cv2.CAP_PROP_EXPOSURE,
}


def list_available_cameras(max_index: int = 5) -> list[tuple[int, str]]:
    """Probe a small range of camera indices and return the ones that opened.

    Names come back as plain ``Camera N`` labels. OpenCV doesn't
    have a portable way to ask the OS for a device's real name,
    and Qt's :class:`~PySide6.QtMultimedia.QMediaDevices` doesn't
    necessarily list cameras in the same order, so mixing the two
    would attach the wrong name to the wrong index.

    Probing is noisy at the C level. OpenCV writes a line to
    stderr for every index that fails to open, and on macOS
    AVFoundation prints "out device of bound" before OpenCV's own
    message. Neither makes it through Python's logging, so the
    probe redirects file descriptor 2 to ``/dev/null`` for the
    duration of the call. Restored on exit so later log lines
    still reach the terminal.
    """
    with _silenced_native_stderr():
        found: list[tuple[int, str]] = []
        for idx in range(max_index):
            cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
            try:
                if cap.isOpened():
                    found.append((idx, f"Camera {idx}"))
            finally:
                cap.release()
        return found


@contextlib.contextmanager
def _silenced_native_stderr() -> Iterator[None]:
    """Send file descriptor 2 to the null device for the duration of the block.

    Native libraries (AVFoundation on macOS, V4L2 on Linux) write
    to stderr through the C runtime, which bypasses Python's
    ``sys.stderr`` and ``logging``. Swapping the underlying file
    descriptor catches both. Always restored on exit.
    """
    devnull_path = "nul" if sys.platform == "win32" else "/dev/null"
    saved_fd = os.dup(2)
    try:
        with open(devnull_path, "wb") as devnull:
            os.dup2(devnull.fileno(), 2)
            try:
                yield
            finally:
                os.dup2(saved_fd, 2)
    finally:
        os.close(saved_fd)


class CameraCapture(QObject):
    """Reads frames from a camera on a background thread.

    The worker emits ``frame_ready(frame_bgr, timestamp,
    frame_id)`` for each frame and ``opened(width, height, fps)``
    once the device is up. Errors come out on ``error(message)``.
    """

    frame_ready = Signal(np.ndarray, float, int)
    opened = Signal(int, int, float)
    closed = Signal()
    error = Signal(str)

    def __init__(self, config: CameraConfig | None = None) -> None:
        super().__init__()
        self._config = config or CameraConfig()
        self._thread: QThread | None = None
        self._running = False
        self._cap: cv2.VideoCapture | None = None
        self._frame_id = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        thread = QThread()
        self.moveToThread(thread)
        thread.started.connect(self._run)
        self._thread = thread
        self._running = True
        thread.start()

    def stop(self) -> None:
        """Tell the worker thread to wind up and wait for it.

        The QObject keeps its thread affinity on the now-finished
        worker thread, but the instance is single-use anyway so
        that doesn't matter. We don't try to ``moveToThread`` back
        to the calling thread because Qt would warn (``stop`` runs
        on the main thread, the object lives on the worker).
        """
        self._running = False
        thread = self._thread
        if thread is None:
            return
        thread.quit()
        thread.wait(2000)
        self._thread = None

    def update_config(self, config: CameraConfig) -> None:
        """Swap the config in. Takes effect on the next ``start``."""
        if self._running:
            log.warning("Camera config changed while running. Restart to apply")
        self._config = config

    @property
    def device_index(self) -> int:
        """The device index this capture was built against."""
        return self._config.device_index

    def set_property(self, name: str, value: float | None) -> bool:
        """Adjust a hardware property on a running capture.

        Returns ``True`` when the call succeeded. Pass ``None`` to leave
        the property at the camera default the next time capture starts.
        """
        if name not in _PROPERTIES:
            raise ValueError(f"Unknown camera property: {name}")
        setattr(self._config, name, value)
        cap = self._cap
        if cap is None or value is None:
            return False
        try:
            return bool(cap.set(_PROPERTIES[name], float(value)))
        except Exception as exc:  # pragma: no cover - driver dependent
            log.debug("Could not set %s: %s", name, exc)
            return False

    def get_property(self, name: str) -> float | None:
        """Read back the current camera value for a property.

        Returns ``None`` when the property is unsupported or the device
        isn't open. Useful for showing the user what the driver actually
        accepted, which is sometimes different from what was requested.
        """
        if name not in _PROPERTIES:
            raise ValueError(f"Unknown camera property: {name}")
        cap = self._cap
        if cap is None:
            return None
        try:
            value = cap.get(_PROPERTIES[name])
        except Exception:  # pragma: no cover - driver dependent
            return None
        # OpenCV returns 0.0 for unsupported properties on some drivers,
        # but also for properties that genuinely sit at zero. The two
        # cases are indistinguishable, so return whatever was reported.
        return float(value)

    def _run(self) -> None:
        cfg = self._config
        cap = cv2.VideoCapture(cfg.device_index, cfg.backend)
        if not cap.isOpened():
            self.error.emit(f"Could not open camera {cfg.device_index}")
            return
        self._cap = cap

        if cfg.width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(cfg.width))
        if cfg.height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(cfg.height))
        if cfg.fps:
            cap.set(cv2.CAP_PROP_FPS, float(cfg.fps))

        # Apply optional hardware image controls. These often have driver
        # specific ranges. Ignore failures and let the user retry from
        # preferences if a value is out of range.
        for name, prop in _PROPERTIES.items():
            value = getattr(cfg, name)
            if value is None:
                continue
            try:
                cap.set(prop, float(value))
            except Exception as exc:  # pragma: no cover - driver dependent
                log.debug("Failed to set %s on camera: %s", name, exc)

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        self.opened.emit(width, height, fps)

        consecutive_failures = 0
        try:
            while self._running:
                ok, frame = cap.read()
                ts = time.monotonic()
                if not ok or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures > 30:
                        self.error.emit("Camera produced no frames")
                        break
                    # A short sleep so the loop doesn't pin a CPU core
                    # if the device dies on us.
                    QThread.msleep(20)
                    continue
                consecutive_failures = 0
                self._frame_id += 1
                self.frame_ready.emit(frame, ts, self._frame_id)
        finally:
            cap.release()
            self._cap = None
            self.closed.emit()
