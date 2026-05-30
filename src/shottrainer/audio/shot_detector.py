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
from scipy.signal import lfilter

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
        # ``lfilter`` carries its delay line in a small ``zi``
        # array. The DC blocker is order 1 (one delay tap on the
        # input, one on the output), so ``zi`` is just a single
        # element.
        self._filter_state: np.ndarray = np.zeros(1, dtype=np.float32)
        # The filter coefficients only depend on
        # ``high_pass_alpha``, so cache them and only rebuild
        # when the alpha changes. The block callback runs
        # roughly a hundred times a second, which would
        # otherwise leak two tiny ndarray allocations per call.
        self._filter_alpha: float | None = None
        self._filter_b: np.ndarray = np.array([1.0, -1.0], dtype=np.float32)
        self._filter_a: np.ndarray = np.array([1.0, 0.0], dtype=np.float32)
        self._refresh_filter_coefficients()

    def _refresh_filter_coefficients(self) -> None:
        """Rebuild the cached ``b`` / ``a`` arrays for the DC blocker."""
        alpha = self.settings.high_pass_alpha
        if alpha == self._filter_alpha:
            return
        self._filter_alpha = alpha
        self._filter_a = np.array([1.0, -alpha], dtype=np.float32)

    def reset(self) -> None:
        """Clear the filter state and the refractory timestamp.

        Call this when starting a new session so an old shot
        timestamp doesn't suppress the first shot of the new one.
        """
        self._last_shot_ts = None
        self._filter_state = np.zeros(1, dtype=np.float32)

    def update_settings(self, settings: ShotDetectorSettings) -> None:
        """Swap in new settings without losing the filter state."""
        self.settings = settings
        self._refresh_filter_coefficients()

    def process_block(self, samples: np.ndarray, block_start_ts: float) -> ShotEvent | None:
        """Process one block of audio and return a shot event if there is one.

        Returns a :class:`ShotEvent` when the block's RMS crosses
        ``settings.threshold`` and we're not still inside the
        refractory window. ``None`` for silent or refractory
        blocks. Multichannel input gets averaged down to mono
        before the filter runs.
        """
        if samples.size == 0:
            return None

        s = self.settings
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        samples = samples.astype(np.float32, copy=False)

        # One-pole DC blocker: ``y[n] = x[n] - x[n-1] + a*y[n-1]``.
        # We express it in transfer-function form for ``lfilter``
        # so the work runs in C: numerator ``[1, -1]`` for the
        # input difference, denominator ``[1, -a]`` for the
        # recursive output. ``zi`` carries the one-sample delay
        # line across blocks so streaming output matches a
        # one-shot filter over the concatenated signal. The
        # coefficients are cached so we don't allocate two tiny
        # float arrays on every block.
        out, self._filter_state = lfilter(
            self._filter_b, self._filter_a, samples, zi=self._filter_state
        )
        out = out.astype(np.float32, copy=False)

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
