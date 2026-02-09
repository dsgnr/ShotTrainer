"""Audio data types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShotEvent:
    timestamp: float
    audio_level: float
    sample_rate: int


@dataclass(slots=True)
class ShotDetectorSettings:
    threshold: float = 0.25         # RMS threshold relative to full scale
    refractory_ms: int = 400         # ignore further triggers within this window
    block_size: int = 1024           # frames per audio callback
    sample_rate: int = 44100
    high_pass_alpha: float = 0.97    # one-pole DC-blocker. Closer to 1.0 = more low cut
