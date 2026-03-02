"""The target display widget.

Renders the scoring rings, the live aim trace, and the shot
markers in target-space millimetres. The widget owns no domain
state of its own beyond the rendering buffers. The caller has
to tell it what to show.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


@dataclass(frozen=True, slots=True)
class TargetRing:
    radius_mm: float
    label: str | None = None


# Default rings are a generic concentric set. Real disciplines configure their own.
DEFAULT_RINGS: tuple[TargetRing, ...] = (
    TargetRing(75.0, "1"),
    TargetRing(60.0, "3"),
    TargetRing(45.0, "5"),
    TargetRing(30.0, "7"),
    TargetRing(15.0, "9"),
    TargetRing(5.0, "X"),
)


@dataclass(frozen=True, slots=True)
class ShotMarker:
    x_mm: float
    y_mm: float
    label: str = ""


class TargetView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

        self._rings: tuple[TargetRing, ...] = DEFAULT_RINGS
        self._extent_mm: float = 90.0
        self._trace: deque[tuple[float, float]] = deque(maxlen=600)
        self._shots: list[ShotMarker] = []
        self._selected_shot: int | None = None
        self._live_aim: tuple[float, float] | None = None
        self._live_aim_manual: bool = False
        self._split_index: int | None = None  # trace index where pre/post divides

    def set_rings(self, rings: Iterable[TargetRing]) -> None:
        self._rings = tuple(rings)
        if self._rings:
            self._extent_mm = max(r.radius_mm for r in self._rings) * 1.15
        self.update()

    def set_extent_mm(self, extent_mm: float) -> None:
        self._extent_mm = max(1.0, extent_mm)
        self.update()

    def set_trace_capacity(self, n: int) -> None:
        self._trace = deque(self._trace, maxlen=max(1, n))

    def append_trace_point(self, x_mm: float, y_mm: float) -> None:
        self._trace.append((x_mm, y_mm))
        self._live_aim = (x_mm, y_mm)
        self.update()

    def set_trace(self, points: Iterable[tuple[float, float]]) -> None:
        self._trace = deque(points, maxlen=self._trace.maxlen)
        self._live_aim = self._trace[-1] if self._trace else None
        self.update()

    def set_split_index(self, index: int | None) -> None:
        """Mark the pre/post divide for replay; ``None`` draws a single colour."""
        self._split_index = index
        self.update()

    def set_live_aim_manual(self, manual: bool) -> None:
        """Mark the live aim cursor as user-picked rather than auto-detected."""
        if self._live_aim_manual != manual:
            self._live_aim_manual = manual
            self.update()

    def clear_trace(self) -> None:
        self._trace.clear()
        self._live_aim = None
        self.update()

    def set_shots(self, shots: Iterable[ShotMarker]) -> None:
        self._shots = list(shots)
        self.update()

    def set_selected_shot(self, index: int | None) -> None:
        self._selected_shot = index
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#f7f7f5"))

        size = min(self.width(), self.height())
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        scale = (size - 16) / (2.0 * self._extent_mm)  # px per mm

        self._draw_rings(painter, cx, cy, scale)
        self._draw_crosshair(painter, cx, cy, size)
        self._draw_trace(painter, cx, cy, scale)
        self._draw_shots(painter, cx, cy, scale)
        self._draw_live_aim(painter, cx, cy, scale)

    def _draw_rings(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        pen = QPen(QColor("#444"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for ring in self._rings:
            r = ring.radius_mm * scale
            painter.drawEllipse(QPointF(cx, cy), r, r)
            if ring.label:
                painter.drawText(QRectF(cx + r - 24, cy - 10, 22, 14), Qt.AlignmentFlag.AlignRight, ring.label)

    def _draw_crosshair(self, painter: QPainter, cx: float, cy: float, size: float) -> None:
        pen = QPen(QColor("#aaa"))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(cx - size / 2), int(cy), int(cx + size / 2), int(cy))
        painter.drawLine(int(cx), int(cy - size / 2), int(cx), int(cy + size / 2))

    def _draw_trace(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        if len(self._trace) < 2:
            return
        pre_pen = QPen(QColor(60, 120, 200, 180))
        pre_pen.setWidth(1)
        post_pen = QPen(QColor(40, 160, 90, 200))
        post_pen.setWidth(1)
        split = self._split_index

        prev: QPointF | None = None
        for i, (x_mm, y_mm) in enumerate(self._trace):
            p = QPointF(cx + x_mm * scale, cy + y_mm * scale)
            if prev is not None:
                if split is None or i <= split:
                    painter.setPen(pre_pen)
                else:
                    painter.setPen(post_pen)
                painter.drawLine(prev, p)
            prev = p

    def _draw_shots(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        for i, shot in enumerate(self._shots):
            x = cx + shot.x_mm * scale
            y = cy + shot.y_mm * scale
            selected = i == self._selected_shot
            colour = QColor("#c0392b") if selected else QColor("#e74c3c")
            painter.setBrush(colour)
            pen = QPen(QColor("#7b1f15"))
            pen.setWidth(2 if selected else 1)
            painter.setPen(pen)
            radius = 6.0 if selected else 4.0
            painter.drawEllipse(QPointF(x, y), radius, radius)
            if shot.label:
                painter.setPen(QColor("#222"))
                painter.drawText(QRectF(x + 6, y - 16, 30, 14), Qt.AlignmentFlag.AlignLeft, shot.label)

    def _draw_live_aim(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        if self._live_aim is None:
            return
        x = cx + self._live_aim[0] * scale
        y = cy + self._live_aim[1] * scale
        pen = QPen(QColor("#f39c12") if self._live_aim_manual else QColor("#27ae60"))
        pen.setWidth(2)
        if self._live_aim_manual:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(x, y), 5.0, 5.0)
