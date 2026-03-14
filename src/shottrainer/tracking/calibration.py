"""Pixel to millimetre conversion.

Calibration is derived from a single circle of known diameter printed on
the target sheet. The user shows the circle to the camera and the app
converts the detected radius (in pixels) into a millimetre-per-pixel
scale, with the origin set to the circle's centre in the image.

Convention: the camera is mounted on the rifle, so target motion in the
frame is the *inverse* of the rifle's aim motion. We bake that sign flip
into the calibration by storing a negative ``mm_per_pixel``: a pixel to
the right of the origin in the image reports as a negative mm offset,
i.e. the rifle is aimed *left* of the target centre, and vice versa.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LinearCalibration:
    """Uniform scale calibration with origin at the calibration circle."""

    mm_per_pixel: float
    origin_px: tuple[float, float] = (0.0, 0.0)
    # Diameter of the calibration circle, in millimetres. Kept for
    # diagnostics and so a recalibration can default to the same size.
    diameter_mm: float | None = None

    def to_mm(self, x_px: float, y_px: float) -> tuple[float, float]:
        ox, oy = self.origin_px
        return ((x_px - ox) * self.mm_per_pixel, (y_px - oy) * self.mm_per_pixel)

    def to_pixels(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        ox, oy = self.origin_px
        return (x_mm / self.mm_per_pixel + ox, y_mm / self.mm_per_pixel + oy)


def fit_circle_calibration(
    centre_px: tuple[float, float],
    radius_px: float,
    diameter_mm: float,
) -> LinearCalibration:
    """Build a calibration from a known-diameter circle's image footprint.

    ``mm_per_pixel`` is the printed diameter divided by the detected
    diameter in pixels, negated to honour the rifle-aim sign convention
    (see module docstring). ``origin_px`` is the circle's centre.
    """
    if radius_px <= 0:
        raise ValueError("radius_px must be positive")
    if diameter_mm <= 0:
        raise ValueError("diameter_mm must be positive")
    diameter_px = 2.0 * float(radius_px)
    scale = float(diameter_mm) / diameter_px
    return LinearCalibration(
        mm_per_pixel=-scale,
        origin_px=(float(centre_px[0]), float(centre_px[1])),
        diameter_mm=float(diameter_mm),
    )
