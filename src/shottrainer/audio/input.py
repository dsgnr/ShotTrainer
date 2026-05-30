"""Microphone input through sounddevice.

The class hosts a streaming callback, runs the detector on each
block of audio, and fires Qt signals when a shot lands. Audio
capture itself runs on PortAudio's own thread. Qt queues the
signals back to the GUI thread so receivers don't have to think
about thread safety.
"""

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
        """Swap in new shot-detector settings.

        Forwards the change to the inner :class:`ShotDetector`.
        The listener itself doesn't keep settings of its own.
        """
        self._settings = settings
        self._detector.update_settings(settings)

    def set_device(self, device: str | int | None) -> None:
        """Pick the input device for the next ``start()``.

        Accepts a numeric sounddevice index, a substring of a
        device name, or ``None`` / ``"default"`` for the system
        default. Takes effect on the next start. A live stream
        won't move to the new device on its own.
        """
        self._device = device

    def start(self) -> None:
        """Open the audio stream and start emitting events.

        Calling ``start`` a second time when a stream is already
        running is a no-op. Errors opening PortAudio land on the
        :attr:`error` signal rather than being raised, so the rest
        of the app keeps working when the user hasn't granted
        microphone access yet.
        """
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
        """Close the audio stream if one is open. Always safe to call."""
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        finally:
            self.stopped.emit()

    def _on_block(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Run the detector and emit Qt signals. Called by sounddevice for each block.

        This callback runs on PortAudio's own thread. Qt queues
        the ``shot_detected`` and ``level`` deliveries to the GUI
        thread so receivers don't need to be thread-safe.
        """
        if status:
            log.debug("audio status: %s", status)

        # PortAudio's own clock and ``time.monotonic`` don't share
        # an origin. Using monotonic here keeps the audio on the
        # same timeline as the camera frames.
        ts = time.monotonic() - frames / float(self._settings.sample_rate)

        block = indata[:, 0] if indata.ndim > 1 else indata
        rms = float(np.sqrt(np.dot(block, block) / block.size)) if block.size else 0.0
        self.level.emit(rms)

        event = self._detector.process_block(block, ts)
        if event is not None:
            self.shot_detected.emit(event)
