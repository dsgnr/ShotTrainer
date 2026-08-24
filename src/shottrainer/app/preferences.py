"""User preferences."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Preferences:
    """Everything the user can change from the Preferences dialog.

    The defaults match a typical air-rifle setup. A forward-facing
    barrel- or rail-mounted camera, a 4.5 mm pellet, and a 60 mm
    tracking circle. A ``camera_id`` of ``None`` means "no camera
    selected", which happens when the previously saved device
    isn't attached any more. The preview pauses until the user
    picks one in the dialog.

    Brightness and contrast are applied in software inside the
    capture pipeline rather than handed to the camera. That way
    they behave the same on every platform and the preview
    reflects them straight away.

    Trace inversion flips the sign of the reported aim coordinates
    on a per-axis basis. It's useful for users whose optics
    (a magnifier, a mirror) reverse the default image-vs-aim
    relationship.
    """

    camera_id: int | None = 0
    camera_rotation: int = 0  # 0, 90, 180 or 270 degrees, clockwise
    camera_flip_h: bool = False
    camera_flip_v: bool = False
    camera_brightness: float = 0.0  # -100..100 additive offset, 0 = no change
    camera_contrast: float = 1.0  # 0.5..2.0 multiplier, 1.0 = no change
    audio_device: str = "default"
    audio_gain: float = 1.0
    shot_threshold: float = 0.25
    shot_refractory_ms: int = 400
    pre_shot_ms: int = 1500
    post_shot_ms: int = 800
    target_face: str = "default"
    shot_diameter_mm: float = 4.5  # air pellet by default. .22 ~= 5.6 mm
    tracking_region_fraction: float = 0.7
    circle_diameter_mm: float = 60.0
    invert_trace_horizontal: bool = False
    invert_trace_vertical: bool = False
    # Show the amber "hold zone" circle on the target view during replay.
    # It marks the pre-shot mean position and tremor radius.
    show_hold_zone: bool = True
