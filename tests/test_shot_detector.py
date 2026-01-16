from __future__ import annotations

import numpy as np
import pytest

from shottrainer.audio.models import ShotDetectorSettings
from shottrainer.audio.shot_detector import ShotDetector


def _silence(n: int) -> np.ndarray:
    return np.zeros(n, dtype=np.float32)


def _impulse(n: int, position: int, amplitude: float = 0.9) -> np.ndarray:
    block = _silence(n)
    block[position] = amplitude
    return block


def test_silence_does_not_trigger():
    det = ShotDetector(ShotDetectorSettings(threshold=0.05, block_size=512, sample_rate=8000))
    assert det.process_block(_silence(512), block_start_ts=0.0) is None


def test_loud_impulse_triggers():
    det = ShotDetector(ShotDetectorSettings(threshold=0.02, block_size=512, sample_rate=8000))
    event = det.process_block(_impulse(512, position=128), block_start_ts=10.0)
    assert event is not None
    # Timestamp should land near sample 128 of an 8 kHz block.
    assert event.timestamp == pytest.approx(10.0 + 128 / 8000, abs=1e-3)
    assert event.audio_level > 0.0


def test_refractory_blocks_immediate_second_trigger():
    settings = ShotDetectorSettings(
        threshold=0.02, block_size=512, sample_rate=8000, refractory_ms=300
    )
    det = ShotDetector(settings)
    first = det.process_block(_impulse(512, 100), block_start_ts=0.0)
    assert first is not None
    # Block immediately after, well within the refractory window.
    second = det.process_block(_impulse(512, 100), block_start_ts=0.05)
    assert second is None


def test_refractory_releases_after_window():
    settings = ShotDetectorSettings(
        threshold=0.02, block_size=512, sample_rate=8000, refractory_ms=200
    )
    det = ShotDetector(settings)
    det.process_block(_impulse(512, 100), block_start_ts=0.0)
    later = det.process_block(_impulse(512, 100), block_start_ts=0.5)
    assert later is not None


def test_quiet_signal_below_threshold():
    det = ShotDetector(ShotDetectorSettings(threshold=0.5, block_size=512, sample_rate=8000))
    rng = np.random.default_rng(0)
    quiet = (rng.normal(0, 0.01, 512)).astype(np.float32)
    assert det.process_block(quiet, block_start_ts=0.0) is None


def test_stereo_input_is_downmixed():
    det = ShotDetector(ShotDetectorSettings(threshold=0.02, block_size=512, sample_rate=8000))
    block = np.zeros((512, 2), dtype=np.float32)
    block[100, 0] = 0.8
    block[100, 1] = 0.8
    event = det.process_block(block, block_start_ts=0.0)
    assert event is not None


def test_reset_clears_refractory():
    settings = ShotDetectorSettings(
        threshold=0.02, block_size=512, sample_rate=8000, refractory_ms=500
    )
    det = ShotDetector(settings)
    det.process_block(_impulse(512, 100), block_start_ts=0.0)
    det.reset()
    again = det.process_block(_impulse(512, 100), block_start_ts=0.05)
    assert again is not None
