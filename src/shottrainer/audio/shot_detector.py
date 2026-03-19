"""Detect a shot in an audio stream.

The detection logic is independent of the audio backend. Feed it
blocks of mono samples (float32 between -1 and +1) and a
timestamp for the start of each block, and it returns shot
events. That makes it easy to test against synthetic signals and
means the input backend can be swapped without touching any of
the detection code.

The strategy is straightforward. High-pass the signal to strip
out DC and low rumble, take the RMS of each block, fire a shot
the moment the RMS crosses the threshold, then ignore any
further triggers for a short refractory window so echoes and
ringing don't double-fire.
"""

from __future__ import annotations

import math

import numpy as np

from .models import ShotDetectorSettings, ShotEvent


class ShotDetector:
    """Spot a sharp shot impulse in a running stream of audio blocks.

    Holds state between calls to :meth:`process_block`. The
    high-pass filter's delay line and the timestamp of the last
    shot for the refractory window. Call :meth:`reset` when a
    new session starts so an old shot timestamp doesn't suppress
    the first shot of the new one.
    """

    def __init__(self, settings: ShotDetectorSettings | None = None) -> None:
        self.settings = settings or ShotDetectorSettings()
        self._last_shot_ts: float | None = None
        self._hp_prev_in: float = 0.0
        self._hp_prev_out: float = 0.0

    def reset(self) -> None:
        self._last_shot_ts = None
        self._hp_prev_in = 0.0
        self._hp_prev_out = 0.0

    def update_settings(self, settings: ShotDetectorSettings) -> None:
        self.settings = settings

    def process_block(self, samples: np.ndarray, block_start_ts: float) -> ShotEvent | None:
        if samples.size == 0:
            return None

        s = self.settings
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        samples = samples.astype(np.float32, copy=False)

        # One-pole DC blocker: y[n] = x[n] - x[n-1] + a * y[n-1]
        a = s.high_pass_alpha
        out = np.empty_like(samples)
        prev_in = self._hp_prev_in
        prev_out = self._hp_prev_out
        for i, x in enumerate(samples):
            y = x - prev_in + a * prev_out
            out[i] = y
            prev_in = x
            prev_out = y
        self._hp_prev_in = float(prev_in)
        self._hp_prev_out = float(prev_out)

        rms = float(np.sqrt(np.mean(out * out))) if out.size else 0.0
        if not math.isfinite(rms) or rms < s.threshold:
            return None

        # Refractory check.
        if self._last_shot_ts is not None:
            elapsed_ms = (block_start_ts - self._last_shot_ts) * 1000.0
            if elapsed_ms < s.refractory_ms:
                return None

        # Pin the timestamp to the loudest sample in the block.
        idx = int(np.argmax(np.abs(out)))
        sample_offset = idx / float(s.sample_rate)
        ts = block_start_ts + sample_offset
        self._last_shot_ts = ts
        return ShotEvent(timestamp=ts, audio_level=rms, sample_rate=s.sample_rate)
