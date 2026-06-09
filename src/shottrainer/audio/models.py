"""Audio data types, with no sounddevice or PortAudio dependencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShotEvent:
    """A single detected shot event with its timing and level.

    ``timestamp`` is on the same monotonic clock as the tracking
    samples so audio and video line up on a shared timeline.
    ``audio_level`` is the RMS of the filtered block that triggered
    the detection, in the range 0.0..1.0.
    """

    timestamp: float
    audio_level: float
    sample_rate: int


@dataclass(slots=True)
class ShotDetectorSettings:
    """Tunable parameters for the audio shot detector.

    ``threshold`` is the RMS level (0.0..1.0) above which a block
    counts as a shot. ``refractory_ms`` is the minimum gap between
    two consecutive detections, preventing echoes and ringing from
    double-firing. ``high_pass_alpha`` controls the one-pole DC
    blocker; closer to 1.0 removes more low-frequency rumble.
    """

    threshold: float = 0.25
    refractory_ms: int = 400
    block_size: int = 1024
    sample_rate: int = 44100
    high_pass_alpha: float = 0.97
