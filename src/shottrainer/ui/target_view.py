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

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
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
    score: str = ""


# Colour ramp for scoring shots. Tens and inner-tens are
# bright gold, the mid-rings are warm, low rings are dim, and
# misses (or unscored shots) come out neutral red so they're
# still visible. Anything we don't recognise falls through to
# the miss colour.
_SCORE_COLOURS: dict[str, str] = {
    "X": "#f1c40f",
    "10": "#f1c40f",
    "9": "#f39c12",
    "8": "#e67e22",
    "7": "#d35400",
    "6": "#c0392b",
    "5": "#a33223",
    "4": "#8a2a1d",
    "3": "#732417",
    "2": "#5c1d12",
    "1": "#451609",
}
_MISS_COLOUR = "#7f8c8d"


def colour_for_score(score: str) -> str:
    """Return a hex colour for a ring label.

    Federation labels (1..10, X) and decimal sub-rings come out
    on a warm-to-bright ramp. Anything else (empty labels,
    custom strings, misses) falls back to a neutral grey so it
    stays visible without looking like a high-value shot.
    """
    if not score:
        return _MISS_COLOUR
    upper = score.upper()
    if upper in _SCORE_COLOURS:
        return _SCORE_COLOURS[upper]
    # Decimal labels like "10.5" or "9.7" use the colour of
    # their integer part.
    head = upper.split(".", 1)[0]
    return _SCORE_COLOURS.get(head, _MISS_COLOUR)


class TargetView(QWidget):
    extent_changed = Signal(float)

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
        self._playhead_index: int | None = None
        self._hold_zone: tuple[float, float, float] | None = None  # (cx, cy, r) in mm
        self._shot_diameter_mm: float = 4.5

    def set_rings(self, rings: Iterable[TargetRing]) -> None:
        self._rings = tuple(rings)
        if self._rings:
            self._extent_mm = max(r.radius_mm for r in self._rings) * 1.15
        self.update()

    def set_extent_mm(self, extent_mm: float) -> None:
        self._extent_mm = max(1.0, extent_mm)
        self.update()

    @property
    def extent_mm(self) -> float:
        return self._extent_mm

    def set_trace_capacity(self, n: int) -> None:
        self._trace = deque(self._trace, maxlen=max(1, n))

    def append_trace_point(self, x_mm: float, y_mm: float) -> None:
        self._trace.append((x_mm, y_mm))
        self._live_aim = (x_mm, y_mm)
        self.update()

    def set_trace(self, points: Iterable[tuple[float, float]]) -> None:
        self._trace = deque(points, maxlen=self._trace.maxlen)
        self._live_aim = self._trace[-1] if self._trace else None
        self._playhead_index = None
        self.update()

    def set_split_index(self, index: int | None) -> None:
        """Mark the pre/post divide for replay; ``None`` draws a single colour."""
        self._split_index = index
        self.update()

    def set_playhead_index(self, index: int | None) -> None:
        """Highlight a single trace sample as the replay cursor."""
        if index != self._playhead_index:
            self._playhead_index = index
            self.update()

    def set_live_aim_manual(self, manual: bool) -> None:
        """Mark the live aim cursor as user-picked rather than auto-detected."""
        if self._live_aim_manual != manual:
            self._live_aim_manual = manual
            self.update()

    def set_hold_zone(self, centre: tuple[float, float] | None, radius_mm: float = 0.0) -> None:
        """Overlay the steady-hold zone (centre and radius in mm).

        Pass ``None`` to clear the overlay.
        """
        if centre is None or radius_mm <= 0:
            self._hold_zone = None
        else:
            self._hold_zone = (centre[0], centre[1], radius_mm)
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

    def set_shot_diameter_mm(self, diameter_mm: float) -> None:
        self._shot_diameter_mm = max(0.1, float(diameter_mm))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#11161d"))

        size = min(self.width(), self.height())
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        scale = (size - 16) / (2.0 * self._extent_mm)  # px per mm

        # Cream paper-target face fills the visible extent.
        face_radius = self._extent_mm * scale * 0.95
        painter.setBrush(QColor("#f5f1e8"))
        face_pen = QPen(QColor("#1f2228"))
        face_pen.setWidth(1)
        painter.setPen(face_pen)
        painter.drawEllipse(QPointF(cx, cy), face_radius, face_radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        self._draw_rings(painter, cx, cy, scale)
        self._draw_crosshair(painter, cx, cy, size)
        self._draw_hold_zone(painter, cx, cy, scale)
        self._draw_trace(painter, cx, cy, scale)
        self._draw_playhead(painter, cx, cy, scale)
        self._draw_shots(painter, cx, cy, scale)
        self._draw_live_aim(painter, cx, cy, scale)

    def _draw_playhead(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        if self._playhead_index is None or not self._trace:
            return
        i = max(0, min(len(self._trace) - 1, self._playhead_index))
        x_mm, y_mm = self._trace[i]
        x = cx + x_mm * scale
        y = cy + y_mm * scale
        pen = QPen(QColor("#f1c40f"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(x, y), 7.0, 7.0)

    def _draw_hold_zone(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        if self._hold_zone is None:
            return
        zx, zy, r_mm = self._hold_zone
        r = r_mm * scale
        # Faint amber fill so the trace remains the focus.
        fill = QColor(243, 156, 18, 40)
        outline = QColor(243, 156, 18, 160)
        painter.setBrush(fill)
        pen = QPen(outline)
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(cx + zx * scale, cy + zy * scale), r, r)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_rings(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        pen = QPen(QColor("#1f2228"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for ring in self._rings:
            r = ring.radius_mm * scale
            painter.drawEllipse(QPointF(cx, cy), r, r)
            if ring.label:
                painter.drawText(QRectF(cx + r - 24, cy - 10, 22, 14), Qt.AlignmentFlag.AlignRight, ring.label)

    def _draw_crosshair(self, painter: QPainter, cx: float, cy: float, size: float) -> None:
        pen = QPen(QColor("#888888"))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(cx - size / 2), int(cy), int(cx + size / 2), int(cy))
        painter.drawLine(int(cx), int(cy - size / 2), int(cx), int(cy + size / 2))

    def _draw_trace(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        if len(self._trace) < 2:
            return
        pre_pen = QPen(QColor(60, 120, 200, 220))
        pre_pen.setWidth(2)
        pre_pen.setCosmetic(True)
        pre_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pre_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        post_pen = QPen(QColor(40, 160, 90, 230))
        post_pen.setWidth(2)
        post_pen.setCosmetic(True)
        post_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        post_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
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
        # Render shots at the configured projectile diameter, with a minimum
        # pixel size so they remain visible at very wide zoom levels.
        diameter_px = max(4.0, self._shot_diameter_mm * scale)
        radius_px = diameter_px / 2.0
        for i, shot in enumerate(self._shots):
            x = cx + shot.x_mm * scale
            y = cy + shot.y_mm * scale
            selected = i == self._selected_shot
            base = QColor(colour_for_score(shot.score))
            colour = base.darker(115) if selected else base
            painter.setBrush(colour)
            pen = QPen(base.darker(170))
            pen.setWidth(2 if selected else 1)
            painter.setPen(pen)
            r = radius_px * (1.2 if selected else 1.0)
            painter.drawEllipse(QPointF(x, y), r, r)
            if shot.label:
                painter.setPen(QColor("#1f2228"))
                painter.drawText(QRectF(x + r + 4, y - 16, 30, 14), Qt.AlignmentFlag.AlignLeft, shot.label)

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

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 0.9 if delta > 0 else 1.1
        self.set_extent_mm(self._extent_mm * factor)
        self.extent_changed.emit(self._extent_mm)
        event.accept()
