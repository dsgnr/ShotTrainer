"""Camera capture, run on its own Qt thread.

The capture loop sits on a worker thread so the UI never has to
wait for a frame to arrive. Each frame goes out on a Qt signal
together with a monotonic timestamp, which is the same clock the
audio detector and the recorder use, so everything ends up on a
single timeline.

The capture loop is intentionally small. Anything domain related (detection,
calibration, storage) lives elsewhere and consumes the ``frame_ready`` signal.
"""

from __future__ import annotations

import logging
import time
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


def list_available_cameras(max_index: int = 5) -> list[tuple[int, str]]:
    """Probe a small range of camera indices.

    OpenCV does not give names on all platforms, so this returns generic
    labels. Good enough for a device picker.
    """
    found: list[tuple[int, str]] = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
        try:
            if cap.isOpened():
                found.append((idx, f"Camera {idx}"))
        finally:
            cap.release()
    return found


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
        self._running = False
        thread = self._thread
        if thread is None:
            return
        thread.quit()
        thread.wait(2000)
        self.moveToThread(QThread.currentThread())
        self._thread = None

    def update_config(self, config: CameraConfig) -> None:
        """Swap the config in. Takes effect on the next ``start``."""
        if self._running:
            log.warning("Camera config changed while running. Restart to apply")
        self._config = config

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
