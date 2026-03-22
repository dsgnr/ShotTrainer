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

    The hardware image properties (``camera_brightness`` etc.) are
    optional: ``None`` leaves the camera at its driver default.
    Trace inversion flips the per-axis sign of reported aim
    coordinates and is useful when an optical element (a magnifying
    scope, a mirror) reverses the default image-vs-aim relationship.
    """

    camera_id: int | None = 0
    camera_rotation: int = 0  # 0, 90, 180 or 270 degrees, clockwise
    camera_flip_h: bool = False
    camera_flip_v: bool = False
    camera_brightness: float | None = None
    camera_contrast: float | None = None
    camera_saturation: float | None = None
    camera_gain: float | None = None
    camera_exposure: float | None = None
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
