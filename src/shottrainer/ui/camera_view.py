"""Live camera preview widget.

Shows the latest frame plus an optional aim-point overlay. The
widget doesn't know anything about camera capture. The caller
pushes frames in via ``set_frame`` and tracking samples via
``set_aim_point``. That keeps capture, detection and rendering
on different timelines and means the widget is testable without
a real camera.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget


class CameraView(QWidget):
    clicked_at = Signal(float, float)  # image-space coordinates

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

        self._pixmap: QPixmap | None = None
        self._frame_size: tuple[int, int] = (0, 0)
        self._aim_px: tuple[float, float] | None = None
        self._aim_radius_px: float = 0.0
        self._show_overlay: bool = True

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            return
        h, w, _ = frame_bgr.shape
        # QImage wants an RGB byte buffer with a known stride.
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(image.copy())  # detach from numpy buffer
        self._frame_size = (w, h)
        self.update()

    def set_aim_point(self, x_px: float | None, y_px: float | None, radius_px: float = 0.0) -> None:
        if x_px is None or y_px is None:
            self._aim_px = None
        else:
            self._aim_px = (x_px, y_px)
            self._aim_radius_px = radius_px
        self.update()

    def set_overlay_visible(self, visible: bool) -> None:
        self._show_overlay = visible
        self.update()

    def clear(self) -> None:
        self._pixmap = None
        self._aim_px = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        if self._pixmap is None:
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No camera")
            return

        # Letterbox the frame into the widget while preserving aspect ratio.
        target = self.rect()
        scaled = self._pixmap.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        offset_x = (target.width() - scaled.width()) // 2
        offset_y = (target.height() - scaled.height()) // 2
        painter.drawPixmap(offset_x, offset_y, scaled)

        if self._show_overlay and self._aim_px is not None:
            self._draw_aim_overlay(painter, scaled.size().toTuple(), (offset_x, offset_y))

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

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._pixmap is None or event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        target = self.rect()
        scaled = self._pixmap.size().scaled(
            target.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
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
