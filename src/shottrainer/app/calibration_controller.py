"""Apply, persist and report calibrations.

Lives in ``app/`` because it bridges UI status updates with the tracker
and the calibration store. Keeps the main ``AppController`` smaller.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from shottrainer.tracking.calibration import (
    HomographyCalibration,
    LinearCalibration,
    a4_target_corners,
    fit_rifle_homography,
)
from shottrainer.tracking.tracker import Tracker

from .calibration_store import load_calibration, save_calibration

log = logging.getLogger(__name__)


CalibrationLike = LinearCalibration | HomographyCalibration


class CalibrationController:
    """Glue between the UI calibration flow and the tracker / store."""

    def __init__(
        self,
        tracker: Tracker,
        on_status: Callable[[str], None],
        on_message: Callable[[str], None],
        on_persisted: Callable[[], None] | None = None,
    ) -> None:
        self._tracker = tracker
        self._on_status = on_status
        self._on_message = on_message
        self._on_persisted = on_persisted

    def restore_saved(self) -> None:
        """Load any previously saved calibration and apply it to the tracker."""
        saved = load_calibration()
        if saved is None:
            return
        self._tracker.set_calibration(saved)
        self._publish_status(saved)

    def apply_image_points(self, image_points: list[tuple[float, float]]) -> None:
        """Fit a homography from the user's selected points and persist it.

        Uses the rifle-aim convention: the camera is mounted on the
        rifle, so target motion in the frame corresponds to inverted
        aim motion on the target plane.
        """
        try:
            cal = fit_rifle_homography(image_points, a4_target_corners("centre"))
        except Exception as exc:
            self._on_message(f"Calibration failed: {exc}")
            return
        self._tracker.set_calibration(cal)
        self._publish_status(cal)
        try:
            save_calibration(cal)
        except OSError as exc:
            log.warning("Could not save calibration: %s", exc)
        else:
            if self._on_persisted is not None:
                self._on_persisted()
        self._on_message("Calibration applied")

    def _publish_status(self, cal: CalibrationLike) -> None:
        if isinstance(cal, LinearCalibration):
            mm_per_px = cal.mm_per_pixel
        else:
            mm_per_px = cal.diagnostic_mm_per_pixel()
        self._on_status(f"Calibrated: {mm_per_px:.3f} mm/px")
