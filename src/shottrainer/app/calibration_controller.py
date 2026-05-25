"""Apply, persist and report calibrations.

Lives in ``app/`` because it bridges UI status updates with the tracker
and the calibration store. Keeps the main ``AppController`` smaller.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from shottrainer.tracking.calibration import LinearCalibration, fit_circle_calibration
from shottrainer.tracking.tracker import Tracker

from .calibration_store import load_calibration, save_calibration

log = logging.getLogger(__name__)


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

    def apply_circle(
        self,
        centre_px: tuple[float, float],
        radius_px: float,
        diameter_mm: float,
    ) -> None:
        """Build a linear calibration from a known-diameter circle and persist it."""
        try:
            cal = fit_circle_calibration(centre_px, radius_px, diameter_mm)
        except ValueError as exc:
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

    def _publish_status(self, cal: LinearCalibration) -> None:
        # Report the unsigned mm/px so the header stays human-friendly;
        # the sign is an implementation detail of the rifle-aim convention.
        self._on_status(f"Calibrated: {abs(cal.mm_per_pixel):.3f} mm/px")
