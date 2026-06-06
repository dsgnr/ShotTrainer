"""Live camera view.

:class:`RawCameraView` is a base class (inherited from :class:`QWidget`)
that renders frames with aspect-ratio scaling. It's intentionally kept simple.
Used anywhere a plain camera image is needed (popout dialog, preferences preview).

:class:`CameraView` is a child class of :class:`RawCameraView` with
tracking overlays (aim point, reticle, status badge, region rectangle)
and click-to-aim. Used in the main window's left column.

Neither class knows anything about camera capture. The caller pushes
frames in via ``set_frame``. That keeps capture, detection and
rendering on different timelines and means the classes are testable
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


class _StatusStyle(NamedTuple):
    """Badge label and colour for one :data:`TrackingStatus` value."""

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
    """Renders camera frames scaled to fit.

    Satisfies the ``_FrameMirror`` protocol so it can be used as a
    target for the controller's frame mirroring.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

        self._pixmap: QPixmap | None = None
        self._scaled_pixmap: QPixmap | None = None
        self._scaled_for_size: tuple[int, int] = (0, 0)
        self._frame_size: tuple[int, int] = (0, 0)

    def set_frame(self, frame: np.ndarray) -> None:
        """Push a frame into the preview.

        Accepts either a colour BGR frame (``H x W x 3`` uint8)
        or a single-channel greyscale frame (``H x W`` uint8).
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
        """Alias for set_frame (satisfies _FrameMirror protocol)."""
        self.set_frame(frame)

    def push_audio_level(self, level: float) -> None:
        """No-op (satisfies _FrameMirror protocol)."""

    def clear(self) -> None:
        self._pixmap = None
        self._scaled_pixmap = None
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._scaled_pixmap = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        if self._pixmap is None:
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No camera")
            return

        target = self.rect()
        target_size = (target.width(), target.height())
        if self._scaled_pixmap is None or self._scaled_for_size != target_size:
            self._scaled_pixmap = self._pixmap.scaled(
                target.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self._scaled_for_size = target_size
        scaled = self._scaled_pixmap
        offset_x = (target.width() - scaled.width()) // 2
        offset_y = (target.height() - scaled.height()) // 2
        painter.drawPixmap(offset_x, offset_y, scaled)


class CameraView(RawCameraView):
    """Camera preview with tracking overlays and click-to-aim."""

    clicked_at = Signal(float, float)  # image-space coordinates

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._aim_px: tuple[float, float] | None = None
        self._aim_radius_px: float = 0.0
        self._rejected_px: tuple[float, float] | None = None
        self._rejected_radius_px: float = 0.0
        self._status: TrackingStatus | None = None
        self._region_fraction: float = 1.0

    def set_aim_point(self, x_px: float | None, y_px: float | None, radius_px: float = 0.0) -> None:
        if x_px is None or y_px is None:
            self._aim_px = None
        else:
            self._aim_px = (x_px, y_px)
            self._aim_radius_px = radius_px
        self.update()

    def set_rejected_point(
        self, x_px: float | None, y_px: float | None, radius_px: float = 0.0
    ) -> None:
        """Show or hide a marker for a candidate the region rejected."""
        if x_px is None or y_px is None:
            self._rejected_px = None
        else:
            self._rejected_px = (x_px, y_px)
            self._rejected_radius_px = radius_px
        self.update()

    def set_status(self, status: TrackingStatus) -> None:
        if status not in _STATUS_STYLES:
            raise ValueError(f"Unknown tracking status: {status}")
        if status != self._status:
            self._status = status
            self.update()

    def set_region_fraction(self, fraction: float) -> None:
        """Tell the view what fraction of the frame is being tracked."""
        f = max(0.05, min(1.0, float(fraction)))
        if abs(f - self._region_fraction) > 1e-6:
            self._region_fraction = f
            self.update()

    def clear(self) -> None:
        self._aim_px = None
        self._rejected_px = None
        super().clear()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        if self._pixmap is None:
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No camera")
            return

        target = self.rect()
        target_size = (target.width(), target.height())
        if self._scaled_pixmap is None or self._scaled_for_size != target_size:
            self._scaled_pixmap = self._pixmap.scaled(
                target.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self._scaled_for_size = target_size
        scaled = self._scaled_pixmap
        offset_x = (target.width() - scaled.width()) // 2
        offset_y = (target.height() - scaled.height()) // 2
        painter.drawPixmap(offset_x, offset_y, scaled)

        if self._aim_px is not None:
            self._draw_aim_overlay(painter, scaled.size().toTuple(), (offset_x, offset_y))
        if self._rejected_px is not None:
            self._draw_rejected_overlay(painter, scaled.size().toTuple(), (offset_x, offset_y))

        self._draw_centre_reticle(painter, scaled.size().toTuple(), (offset_x, offset_y))
        if self._region_fraction < 0.999:
            self._draw_tracking_region(painter, scaled.size().toTuple(), (offset_x, offset_y))
        if self._status is not None:
            self._draw_status_badge(painter)

    def _draw_tracking_region(
        self,
        painter: QPainter,
        scaled_size: tuple[int, int],
        offset: tuple[int, int],
    ) -> None:
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

    def _draw_centre_reticle(
        self,
        painter: QPainter,
        scaled_size: tuple[int, int],
        offset: tuple[int, int],
    ) -> None:
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
        style = _STATUS_STYLES[self._status]
        margin = 8
        padding_x = 8
        padding_y = 4
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(style.label)
        text_h = metrics.height()
        rect_w = text_w + padding_x * 2
        rect_h = text_h + padding_y
        x = margin
        y = margin

        painter.save()
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(x, y, rect_w, rect_h, 4, 4)
        dot_d = 8
        painter.setBrush(QColor(style.colour))
        painter.drawEllipse(x + 6, y + (rect_h - dot_d) // 2, dot_d, dot_d)
        painter.setPen(QColor("#f7f7f5"))
        painter.drawText(
            x + dot_d + 12,
            y + padding_y // 2 + metrics.ascent(),
            style.label,
        )
        painter.restore()

    def _draw_aim_overlay(
        self,
        painter: QPainter,
        scaled_size: tuple[int, int],
        offset: tuple[int, int],
    ) -> None:
        assert self._aim_px is not None
        fw, fh = self._frame_size
        if fw == 0 or fh == 0:
            return
        sw, sh = scaled_size
        ox, oy = offset
        sx = ox + self._aim_px[0] * sw / fw
        sy = oy + self._aim_px[1] * sh / fh
        radius = max(6.0, self._aim_radius_px * sw / fw)

        pen = QPen(Qt.GlobalColor.green)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawEllipse(int(sx - radius), int(sy - radius), int(radius * 2), int(radius * 2))
        painter.drawLine(int(sx - radius - 6), int(sy), int(sx - radius + 2), int(sy))
        painter.drawLine(int(sx + radius - 2), int(sy), int(sx + radius + 6), int(sy))
        painter.drawLine(int(sx), int(sy - radius - 6), int(sx), int(sy - radius + 2))
        painter.drawLine(int(sx), int(sy + radius - 2), int(sx), int(sy + radius + 6))

    def _draw_rejected_overlay(
        self,
        painter: QPainter,
        scaled_size: tuple[int, int],
        offset: tuple[int, int],
    ) -> None:
        assert self._rejected_px is not None
        fw, fh = self._frame_size
        if fw == 0 or fh == 0:
            return
        sw, sh = scaled_size
        ox, oy = offset
        sx = ox + self._rejected_px[0] * sw / fw
        sy = oy + self._rejected_px[1] * sh / fh
        radius = max(6.0, self._rejected_radius_px * sw / fw)

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

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._pixmap is None:
            return
        pos = event.position()
        target = self.rect()
        scaled = self._pixmap.size().scaled(target.size(), Qt.AspectRatioMode.KeepAspectRatio)
        offset_x = (target.width() - scaled.width()) // 2
        offset_y = (target.height() - scaled.height()) // 2
        if not (offset_x <= pos.x() < offset_x + scaled.width()):
            return
        if not (offset_y <= pos.y() < offset_y + scaled.height()):
            return
        fw, fh = self._frame_size
        sx = (pos.x() - offset_x) * fw / scaled.width()
        sy = (pos.y() - offset_y) * fh / scaled.height()
        self.clicked_at.emit(float(sx), float(sy))
