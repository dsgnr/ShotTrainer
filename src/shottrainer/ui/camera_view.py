"""Live camera preview widgets.

Two levels:

- ``RawCameraView`` renders frames with aspect-ratio scaling and
  nothing else. Used anywhere a plain camera image is needed (popout
  dialog, preferences preview).

- ``CameraView`` extends it with tracking overlays (aim point,
  reticle, status badge, region rectangle) and click-to-aim. Used in
  the main window's left column.

Neither widget knows anything about camera capture. The caller pushes
frames in via ``set_frame``. That keeps capture, detection and
rendering on different timelines and means the widgets are testable
without a real camera.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

TrackingStatus = Literal["idle", "tracking", "lost", "manual", "rejected"]

_Size = tuple[int, int]
_Offset = tuple[int, int]


class _StatusStyle(NamedTuple):
    """Visual properties for a tracking status badge."""

    label: str
    colour: str


_STATUS_STYLES: dict[str, _StatusStyle] = {
    "idle": _StatusStyle("Idle", "#888888"),
    "tracking": _StatusStyle("Tracking", "#27ae60"),
    "lost": _StatusStyle("No target", "#e67e22"),
    "manual": _StatusStyle("Manual aim", "#f39c12"),
    "rejected": _StatusStyle("Outside region", "#d35400"),
}


class RawCameraView(QWidget):
    """Renders camera frames scaled to fit. No overlays.

    Satisfies the ``_FrameMirror`` protocol via ``push_frame`` and
    ``push_audio_level``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

        self._pixmap: QPixmap | None = None
        self._scaled_pixmap: QPixmap | None = None
        self._scaled_for_size: _Size = (0, 0)
        self._frame_size: _Size = (0, 0)

    def set_frame(self, frame: np.ndarray) -> None:
        """Push a new camera frame into the preview.

        Args:
            frame: Either a greyscale (H, W) uint8 array or a BGR
                colour (H, W, 3) uint8 array. Other shapes are
                silently ignored.
        """
        if frame.ndim == 2 and frame.dtype == np.uint8:
            h, w = frame.shape
            image = QImage(frame.data, w, h, w, QImage.Format.Format_Grayscale8)
        elif frame.ndim == 3 and frame.shape[2] == 3:
            h, w, _ = frame.shape
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        else:
            return

        self._pixmap = QPixmap.fromImage(image.copy())
        self._scaled_pixmap = None
        self._frame_size = (w, h)
        self.update()

    def push_frame(self, frame: np.ndarray) -> None:
        """Alias for ``set_frame``. Satisfies ``_FrameMirror`` protocol."""
        self.set_frame(frame)

    def push_audio_level(self, level: float) -> None:
        """No-op. Satisfies ``_FrameMirror`` protocol."""

    def clear(self) -> None:
        """Remove the current frame and repaint as blank."""
        self._pixmap = None
        self._scaled_pixmap = None
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Invalidate the scaled pixmap cache on resize."""
        self._scaled_pixmap = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw the scaled frame centred on a black background."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        if self._pixmap is None:
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No camera")
            return

        scaled = self._ensure_scaled_pixmap()
        offset_x = (self.width() - scaled.width()) // 2
        offset_y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(offset_x, offset_y, scaled)

    def _ensure_scaled_pixmap(self) -> QPixmap:
        """Rebuild the cached scaled pixmap if the widget size changed.

        Must only be called when ``_pixmap`` is not None.

        Returns:
            The cached scaled pixmap.
        """
        assert self._pixmap is not None
        target_size = (self.width(), self.height())
        if self._scaled_pixmap is None or self._scaled_for_size != target_size:
            self._scaled_pixmap = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self._scaled_for_size = target_size
        return self._scaled_pixmap


class CameraView(RawCameraView):
    """Camera preview with tracking overlays and click-to-aim.

    Extends ``RawCameraView`` with aim point, rejected marker, centre
    reticle, tracking region rectangle, status badge and click-to-aim.
    """

    clicked_at = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._aim_px: tuple[float, float] | None = None
        self._aim_radius_px: float = 0.0
        self._rejected_px: tuple[float, float] | None = None
        self._rejected_radius_px: float = 0.0
        self._status: TrackingStatus | None = None
        self._region_fraction: float = 1.0
        self._zero_marker_px: tuple[float, float] | None = None
        self._manual_zero_active: bool = False

    def set_aim_point(self, x_px: float | None, y_px: float | None, radius_px: float = 0.0) -> None:
        """Set or clear the detected aim point overlay.

        Args:
            x_px: X position in frame pixels, or None to clear.
            y_px: Y position in frame pixels, or None to clear.
            radius_px: Detected circle radius in frame pixels.
        """
        if x_px is None or y_px is None:
            self._aim_px = None
        else:
            self._aim_px = (x_px, y_px)
            self._aim_radius_px = radius_px
        self.update()

    def set_rejected_point(
        self, x_px: float | None, y_px: float | None, radius_px: float = 0.0
    ) -> None:
        """Set or clear the rejected candidate marker.

        Drawn as an amber dashed circle with a slash to show that
        something was found but ignored (outside the tracking region).

        Args:
            x_px: X position in frame pixels, or None to clear.
            y_px: Y position in frame pixels, or None to clear.
            radius_px: Detected circle radius in frame pixels.
        """
        if x_px is None or y_px is None:
            self._rejected_px = None
        else:
            self._rejected_px = (x_px, y_px)
            self._rejected_radius_px = radius_px
        self.update()

    def set_status(self, status: TrackingStatus) -> None:
        """Update the tracking status badge.

        Args:
            status: One of the valid TrackingStatus literals.

        Raises:
            ValueError: If status is not a recognised value.
        """
        if status not in _STATUS_STYLES:
            raise ValueError(f"Unknown tracking status: {status}")
        if status != self._status:
            self._status = status
            self.update()

    def set_region_fraction(self, fraction: float) -> None:
        """Set the tracking region as a fraction of the frame.

        Drawn as a dashed rectangle. Clamped to [0.05, 1.0].

        Args:
            fraction: Fraction of the frame used for tracking.
        """
        f = max(0.05, min(1.0, float(fraction)))
        if abs(f - self._region_fraction) > 1e-6:
            self._region_fraction = f
            self.update()

    def set_zero_marker(self, x_px: float | None, y_px: float | None) -> None:
        """Show a marker at the user's chosen zero point in frame pixels.

        Pass ``None`` to either argument to remove the marker. The
        controller works the position out from the current detected
        circle and the saved zero offset, so the marker tracks the
        target as the camera moves.
        """
        new = None if x_px is None or y_px is None else (float(x_px), float(y_px))
        if new != self._zero_marker_px:
            self._zero_marker_px = new
            self.update()

    def set_manual_zero_active(self, active: bool) -> None:
        """Show or hide the "Manual zero" indicator."""
        if active != self._manual_zero_active:
            self._manual_zero_active = active
            self.update()

    def clear(self) -> None:
        """Clear overlays and the frame."""
        self._aim_px = None
        self._rejected_px = None
        super().clear()

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw the frame and all tracking overlays."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        if self._pixmap is None:
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No camera")
            return

        scaled = self._ensure_scaled_pixmap()
        offset_x = (self.width() - scaled.width()) // 2
        offset_y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(offset_x, offset_y, scaled)

        size = scaled.size().toTuple()
        offset = (offset_x, offset_y)

        if self._aim_px is not None:
            self._draw_aim_overlay(painter, size, offset)
        if self._rejected_px is not None:
            self._draw_rejected_overlay(painter, size, offset)

        self._draw_centre_reticle(painter, size, offset)
        if self._zero_marker_px is not None:
            self._draw_zero_marker(painter, size, offset)
        if self._region_fraction < 0.999:
            self._draw_tracking_region(painter, size, offset)
        if self._status is not None:
            self._draw_status_badge(painter)
        if self._manual_zero_active:
            self._draw_manual_zero_badge(painter)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Emit ``clicked_at`` with image-space coordinates on left click."""
        if event.button() != Qt.MouseButton.LeftButton or self._pixmap is None:
            return

        pos = event.position()
        scaled = self._pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        offset_x = (self.width() - scaled.width()) // 2
        offset_y = (self.height() - scaled.height()) // 2

        if not (offset_x <= pos.x() < offset_x + scaled.width()):
            return
        if not (offset_y <= pos.y() < offset_y + scaled.height()):
            return

        fw, fh = self._frame_size
        sx = (pos.x() - offset_x) * fw / scaled.width()
        sy = (pos.y() - offset_y) * fh / scaled.height()
        self.clicked_at.emit(float(sx), float(sy))

    def _draw_tracking_region(self, painter: QPainter, scaled_size: _Size, offset: _Offset) -> None:
        """Draw a dashed rectangle showing the active tracking region."""
        sw, sh = scaled_size
        ox, oy = offset
        rw = sw * self._region_fraction
        rh = sh * self._region_fraction
        x = ox + (sw - rw) / 2.0
        y = oy + (sh - rh) / 2.0

        pen = QPen(QColor(255, 255, 255, 90))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(int(x), int(y), int(rw), int(rh))

    def _draw_centre_reticle(self, painter: QPainter, scaled_size: _Size, offset: _Offset) -> None:
        """Draw a crosshair reticle at the frame centre."""
        sw, sh = scaled_size
        ox, oy = offset
        cx = ox + sw / 2.0
        cy = oy + sh / 2.0
        radius = max(20.0, min(sw, sh) * 0.05)
        gap = radius * 0.35

        pen = QPen(QColor(255, 255, 255, 200))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))
        painter.drawLine(int(cx - radius - 6), int(cy), int(cx - gap), int(cy))
        painter.drawLine(int(cx + gap), int(cy), int(cx + radius + 6), int(cy))
        painter.drawLine(int(cx), int(cy - radius - 6), int(cx), int(cy - gap))
        painter.drawLine(int(cx), int(cy + gap), int(cx), int(cy + radius + 6))

    def _draw_status_badge(self, painter: QPainter) -> None:
        """Draw the tracking status pill in the top-left corner."""
        assert self._status is not None
        style = _STATUS_STYLES[self._status]
        margin = 8
        padding_x = 8
        padding_y = 4
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(style.label)
        rect_w = text_w + padding_x * 2
        rect_h = metrics.height() + padding_y

        painter.save()
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(margin, margin, rect_w, rect_h, 4, 4)

        dot_d = 8
        painter.setBrush(QColor(style.colour))
        painter.drawEllipse(margin + 6, margin + (rect_h - dot_d) // 2, dot_d, dot_d)
        painter.setPen(QColor("#f7f7f5"))
        painter.drawText(
            margin + dot_d + 12,
            margin + padding_y // 2 + metrics.ascent(),
            style.label,
        )
        painter.restore()

    def _draw_zero_marker(self, painter: QPainter, scaled_size: _Size, offset: _Offset) -> None:
        """Draw a small magenta cross at the user's chosen zero point."""
        assert self._zero_marker_px is not None
        sx, sy, _ = self._to_widget_coords(self._zero_marker_px, 0.0, scaled_size, offset)
        outline = QPen(QColor(0, 0, 0, 200))
        outline.setWidth(3)
        line = QPen(QColor("#ff1493"))
        line.setWidth(2)
        arm = 9.0
        painter.save()
        for pen in (outline, line):
            painter.setPen(pen)
            painter.drawLine(int(sx - arm), int(sy), int(sx + arm), int(sy))
            painter.drawLine(int(sx), int(sy - arm), int(sx), int(sy + arm))
        painter.restore()

    def _draw_manual_zero_badge(self, painter: QPainter) -> None:
        """Draw a small "Manual zero" badge in the bottom-left corner."""
        text = "Manual zero"
        margin = 8
        padding_x = 8
        padding_y = 4
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        rect_w = text_w + padding_x * 2
        rect_h = metrics.height() + padding_y
        x = margin
        y = self.height() - margin - rect_h

        painter.save()
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(x, y, rect_w, rect_h, 4, 4)

        dot_d = 8
        painter.setBrush(QColor("#ff1493"))
        painter.drawEllipse(x + 6, y + (rect_h - dot_d) // 2, dot_d, dot_d)
        painter.setPen(QColor("#f7f7f5"))
        painter.drawText(
            x + dot_d + 12,
            y + padding_y // 2 + metrics.ascent(),
            text,
        )
        painter.restore()

    def _draw_aim_overlay(self, painter: QPainter, scaled_size: _Size, offset: _Offset) -> None:
        """Draw the green aim-point circle with crosshair ticks."""
        assert self._aim_px is not None
        sx, sy, radius = self._to_widget_coords(
            self._aim_px, self._aim_radius_px, scaled_size, offset
        )
        if radius == 0.0:
            return

        pen = QPen(Qt.GlobalColor.green)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawEllipse(int(sx - radius), int(sy - radius), int(radius * 2), int(radius * 2))
        painter.drawLine(int(sx - radius - 6), int(sy), int(sx - radius + 2), int(sy))
        painter.drawLine(int(sx + radius - 2), int(sy), int(sx + radius + 6), int(sy))
        painter.drawLine(int(sx), int(sy - radius - 6), int(sx), int(sy - radius + 2))
        painter.drawLine(int(sx), int(sy + radius - 2), int(sx), int(sy + radius + 6))

    def _draw_rejected_overlay(
        self, painter: QPainter, scaled_size: _Size, offset: _Offset
    ) -> None:
        """Draw an amber dashed circle with a slash for a rejected candidate."""
        assert self._rejected_px is not None
        sx, sy, radius = self._to_widget_coords(
            self._rejected_px, self._rejected_radius_px, scaled_size, offset
        )
        if radius == 0.0:
            return

        pen = QPen(QColor("#d35400"))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.save()
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(int(sx - radius), int(sy - radius), int(radius * 2), int(radius * 2))
        slash = radius * 0.7
        painter.drawLine(int(sx - slash), int(sy + slash), int(sx + slash), int(sy - slash))
        painter.restore()

    def _to_widget_coords(
        self,
        point_px: tuple[float, float],
        radius_px: float,
        scaled_size: _Size,
        offset: _Offset,
    ) -> tuple[float, float, float]:
        """Convert frame-space coordinates to widget-space.

        Args:
            point_px: (x, y) in frame pixels.
            radius_px: Circle radius in frame pixels.
            scaled_size: (width, height) of the scaled pixmap.
            offset: (x, y) offset of the pixmap within the widget.

        Returns:
            (widget_x, widget_y, widget_radius), or (0, 0, 0) if
            the frame size is unknown.
        """
        fw, fh = self._frame_size
        if fw == 0 or fh == 0:
            return (0.0, 0.0, 0.0)
        sw, sh = scaled_size
        ox, oy = offset
        sx = ox + point_px[0] * sw / fw
        sy = oy + point_px[1] * sh / fh
        radius = max(6.0, radius_px * sw / fw)
        return (sx, sy, radius)
