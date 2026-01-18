"""Microphone input through sounddevice."""

from __future__ import annotations

import logging
import time

import numpy as np
from PySide6.QtCore import QObject, Signal

from .models import ShotDetectorSettings, ShotEvent
from .shot_detector import ShotDetector

log = logging.getLogger(__name__)


def list_audio_inputs() -> list[str]:
    """Return the names of every input-capable audio device.

    Falls back to a single ``"default"`` entry when sounddevice
    isn't installed or PortAudio can't enumerate devices.
    """
    try:
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - environment dependent
        log.warning("sounddevice unavailable: %s", exc)
        return ["default"]

    try:
        devices = sd.query_devices()
    except Exception as exc:  # pragma: no cover
        log.warning("Could not enumerate audio devices: %s", exc)
        return ["default"]

    names = ["default"]
    for d in devices:
        if d.get("max_input_channels", 0) > 0:
            names.append(d["name"])
    return names


class AudioShotListener(QObject):
    shot_detected = Signal(ShotEvent)
    level = Signal(float)
    started = Signal()
    stopped = Signal()
    error = Signal(str)

    def __init__(
        self,
        settings: ShotDetectorSettings | None = None,
        device: str | int | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings or ShotDetectorSettings()
        self._detector = ShotDetector(self._settings)
        self._device = device
        self._stream = None  # type: ignore[assignment]

    def update_settings(self, settings: ShotDetectorSettings) -> None:
        self._settings = settings
        self._detector.update_settings(settings)

    def set_device(self, device: str | int | None) -> None:
        self._device = device

    def start(self) -> None:
        if self._stream is not None:
            return
        try:
            import sounddevice as sd
        except Exception as exc:
            self.error.emit(f"sounddevice unavailable: {exc}")
            return

        s = self._settings
        try:
            self._stream = sd.InputStream(
                samplerate=s.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=s.block_size,
                device=self._device if self._device not in (None, "default") else None,
                callback=self._on_block,
            )
            self._stream.start()
            self._detector.reset()
            self.started.emit()
        except Exception as exc:
            self._stream = None
            self.error.emit(f"Could not open microphone: {exc}")

    def stop(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        finally:
            self.stopped.emit()

    def _on_block(self, indata: np.ndarray, frames: int, time_info, status) -> None:  # noqa: ANN001
        if status:
            log.debug("audio status: %s", status)

        # PortAudio's own clock and ``time.monotonic`` don't share
        # an origin. Using monotonic here keeps the audio on the
        # same timeline as the camera frames.
        ts = time.monotonic() - frames / float(self._settings.sample_rate)

        block = indata[:, 0] if indata.ndim > 1 else indata
        rms = float(np.sqrt(np.mean(block * block))) if block.size else 0.0
        self.level.emit(rms)

        event = self._detector.process_block(block, ts)
        if event is not None:
            self.shot_detected.emit(event)
