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
    """Parameters for opening a camera device.

    ``device_index`` maps to an OpenCV capture index. ``width``,
    ``height`` and ``fps`` are requests. The device picks the
    nearest supported mode. Leave them as ``None`` to use the
    device's default.
    """

    device_index: int = 0
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    backend: int = cv2.CAP_ANY


_CACHED_CAMERAS: list[tuple[int, str]] | None = None


def list_available_cameras(
    max_index: int = 5, *, force_refresh: bool = False
) -> list[tuple[int, str]]:
    """Return the list of available cameras as ``(index, name)`` pairs.

    Tries Qt's `QMediaDevices` first since that queries the OS
    device list without opening any device. Falls back to probing
    OpenCV indices when Qt is unavailable or returns nothing.

    The result is cached for the process lifetime because device
    enumeration is slow on macOS (each `VideoCapture` call goes
    through AVFoundation permission checks). Pass
    ``force_refresh=True`` to re-enumerate after the user
    plugs in or removes a device.

    Args:
        max_index: Maximum index to probe in the OpenCV fallback path.
        force_refresh: If True, ignore the cache and re-enumerate.

    Returns:
        A list of ``(device_index, display_name)`` tuples.
    """
    global _CACHED_CAMERAS
    if _CACHED_CAMERAS is not None and not force_refresh:
        return list(_CACHED_CAMERAS)

    cameras = _enumerate_via_qt()
    if not cameras:
        cameras = _enumerate_via_opencv(max_index)

    _CACHED_CAMERAS = cameras
    return list(cameras)


def _enumerate_via_qt() -> list[tuple[int, str]]:
    """Enumerate cameras via Qt's `QMediaDevices`. Fast on all platforms."""
    try:
        from PySide6.QtMultimedia import QMediaDevices
    except ImportError:
        return []
    try:
        inputs = QMediaDevices.videoInputs()
    except Exception:  # pragma: no cover - platform dependent
        log.warning("QMediaDevices.videoInputs() failed", exc_info=True)
        return []
    return [(idx, dev.description() or f"Camera {idx}") for idx, dev in enumerate(inputs)]


def _enumerate_via_opencv(max_index: int) -> list[tuple[int, str]]:
    """Probe OpenCV indices to find available cameras.

    Slow on macOS because each `cv2.VideoCapture` call goes
    through AVFoundation. Used only when Qt enumeration fails.
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
        """Spin up the worker thread and start capturing.

        Each ``CameraCapture`` is single-use. To restart capture
        the caller builds a new instance. Calling ``start`` twice
        on the same instance is a no-op.
        """
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
        if not thread.wait(5000):
            log.warning("Camera thread did not stop within 5s, terminating")
            thread.terminate()
            thread.wait(1000)
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

    def _run(self) -> None:
        """Open the camera and emit frames until stopped. Runs on the worker thread."""
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
