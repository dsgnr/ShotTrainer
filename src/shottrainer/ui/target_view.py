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
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from shottrainer.app.target_faces import TargetRing

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
    """The target display widget rendering rings, trace, and shot markers.

    All coordinates are in target-space millimetres. The widget converts
    to pixels at paint time based on the current zoom extent.
    """

    extent_changed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the target view with default rings and zoom.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

        self._rings: tuple[TargetRing, ...] = DEFAULT_RINGS
        self._extent_mm: float = 90.0
        self._trace: deque[tuple[float, float]] = deque(maxlen=600)
        # Mirror of ``_trace`` split into the three replay phases.
        # Stored in target-space mm. The painter applies the
        # zoom and centre offset at draw time, so a resize or a
        # zoom doesn't need a rebuild. ``append_trace_point``
        # keeps these in step with the deque so the per-paint
        # work stays a single ``drawPolyline`` per phase.
        self._trace_approach: QPolygonF = QPolygonF()
        self._trace_release: QPolygonF = QPolygonF()
        self._trace_follow: QPolygonF = QPolygonF()
        self._shots: list[ShotMarker] = []
        self._selected_shot: int | None = None
        self._live_aim: tuple[float, float] | None = None
        # Replay segmentation. ``_release_index`` marks the moment the
        # shooter is "settling for the shot" (a few hundred ms before
        # the shot itself). ``_shot_index`` marks the shot. Each is
        # ``None`` outside replay. The trace is drawn in three colours
        # so the approach, the release window and the follow-through
        # are visually distinct.
        self._release_index: int | None = None
        self._shot_index: int | None = None
        self._playhead_index: int | None = None
        self._hold_zone: tuple[float, float, float] | None = None  # (cx, cy, r) in mm
        self._shot_diameter_mm: float = 4.5
        # When true, ``_draw_shots`` renders only ``_selected_shot``.
        # Used during replay so the chosen shot's trace isn't competing
        # with other markers from the same session.
        self._isolate_selected_shot: bool = False

    def set_rings(self, rings: Iterable[TargetRing]) -> None:
        """Set the target face rings and auto-adjust the extent.

        Args:
            rings: The ring definitions for the active target face.
        """
        self._rings = tuple(rings)
        if self._rings:
            self._extent_mm = max(r.diameter_mm for r in self._rings) / 2 * 1.15
        self.update()

    def set_extent_mm(self, extent_mm: float) -> None:
        """Set the visible extent (half-width of the view in mm).

        Args:
            extent_mm: Half the visible width/height in mm.
        """
        self._extent_mm = max(1.0, extent_mm)
        self.update()

    @property
    def extent_mm(self) -> float:
        return self._extent_mm

    def reset_extent_to_rings(self) -> None:
        """Reset the visible extent to fit the current rings.

        Uses the same calculation as :meth:`set_rings` so keyboard
        shortcuts and the menu can return the view to a sensible
        default after the user has zoomed in or out.
        """
        if self._rings:
            self._extent_mm = max(r.diameter_mm for r in self._rings) / 2 * 1.15
            self.extent_changed.emit(self._extent_mm)
            self.update()

    def set_trace_capacity(self, n: int) -> None:
        """Set the maximum number of trace samples retained.

        Args:
            n: Maximum trace length (clamped to at least 1).
        """
        capacity = max(1, n)
        self._trace = deque(self._trace, maxlen=capacity)
        self._rebuild_trace_polygons()

    def append_trace_point(self, x_mm: float, y_mm: float) -> None:
        """Append a single point to the live trace.

        Args:
            x_mm: Horizontal offset from centre in mm.
            y_mm: Vertical offset from centre in mm.
        """
        # Drop points well outside the visible target. A noisy
        # detection (a sliver-of-a-pixel ellipse fit, the camera
        # being swept past the target) can land hundreds of mm
        # off-screen. Keeping those points makes every paint
        # walk huge off-widget line segments.
        clip_mm = self._extent_mm * 4.0
        if abs(x_mm) > clip_mm or abs(y_mm) > clip_mm:
            return
        # The deque has a fixed capacity. Once it's full a new
        # point pushes the oldest one out, and the matching
        # polygon needs the same trim. The dropped point always
        # sits at the head of the approach polygon, since phase
        # boundaries shift via ``set_trace_segments`` rather than
        # because of trace age.
        if self._trace.maxlen is not None and len(self._trace) >= self._trace.maxlen:
            if self._trace_approach.size() > 0:
                self._trace_approach.remove(0)
            else:
                # Replay segmentation can leave the approach run
                # empty. A full rebuild is the simplest way back
                # to a consistent state.
                self._rebuild_trace_polygons()
        self._trace.append((x_mm, y_mm))
        self._live_aim = (x_mm, y_mm)
        polygon = self._polygon_for_index(
            len(self._trace) - 1,
            self._trace_approach,
            self._trace_release,
            self._trace_follow,
        )
        polygon.append(QPointF(x_mm, y_mm))
        self.update()

    def set_trace(self, points: Iterable[tuple[float, float]]) -> None:
        """Replace the entire trace with the given points.

        Args:
            points: Iterable of (x_mm, y_mm) positions.
        """
        self._trace = deque(points, maxlen=self._trace.maxlen)
        self._live_aim = self._trace[-1] if self._trace else None
        self._playhead_index = None
        self._rebuild_trace_polygons()
        self.update()

    def set_trace_segments(
        self,
        release_index: int | None,
        shot_index: int | None,
    ) -> None:
        """Mark the boundaries between the trace's three replay phases.

        Approach runs from the start of the window up to ``release_index``.
        Release runs from ``release_index`` to ``shot_index``.
        Follow-through runs after ``shot_index``.

        ``None`` collapses the corresponding boundary. Passing both as
        ``None`` draws the trace in a single colour.
        """
        self._release_index = release_index
        self._shot_index = shot_index
        self._rebuild_trace_polygons()
        self.update()

    def set_isolate_selected_shot(self, isolate: bool) -> None:
        """Hide every shot but the selected one.

        Used during replay so the chosen shot's trace isn't
        drawn over the top of unrelated shot markers from the
        same session.
        """
        if self._isolate_selected_shot != isolate:
            self._isolate_selected_shot = isolate
            self.update()

    def set_playhead_index(self, index: int | None) -> None:
        """Highlight a single trace sample as the replay cursor."""
        if index != self._playhead_index:
            self._playhead_index = index
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
        """Remove all trace points and the live aim dot."""
        self._trace.clear()
        self._live_aim = None
        self._rebuild_trace_polygons()
        self.update()

    def _rebuild_trace_polygons(self) -> None:
        """Rebuild the per-phase polygons from the current ``_trace``.

        The append path keeps the polygons in step with the
        deque on its own. This helper covers everything else.
        A wholesale trace replacement, a phase boundary moving,
        the deque capacity changing, or the empty-approach
        case in ``append_trace_point``.
        """
        approach = QPolygonF()
        release = QPolygonF()
        follow = QPolygonF()
        for i, (x_mm, y_mm) in enumerate(self._trace):
            polygon = self._polygon_for_index(i, approach, release, follow)
            polygon.append(QPointF(x_mm, y_mm))
        self._trace_approach = approach
        self._trace_release = release
        self._trace_follow = follow

    def set_shots(self, shots: Iterable[ShotMarker]) -> None:
        """Replace the shot markers on the target.

        Args:
            shots: Iterable of `ShotMarker` objects.
        """
        self._shots = list(shots)
        self.update()

    def set_selected_shot(self, index: int | None) -> None:
        """Highlight a specific shot marker.

        Args:
            index: Zero-based shot index, or None to clear.
        """
        self._selected_shot = index
        self.update()

    def set_shot_diameter_mm(self, diameter_mm: float) -> None:
        """Set the rendered projectile diameter.

        Args:
            diameter_mm: Projectile diameter in mm (minimum 0.1).
        """
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
            r = ring.diameter_mm / 2 * scale
            painter.drawEllipse(QPointF(cx, cy), r, r)
            if ring.label:
                painter.drawText(
                    QRectF(cx + r - 24, cy - 10, 22, 14), Qt.AlignmentFlag.AlignRight, ring.label
                )

    def _draw_crosshair(self, painter: QPainter, cx: float, cy: float, size: float) -> None:
        pen = QPen(QColor("#888888"))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(cx - size / 2), int(cy), int(cx + size / 2), int(cy))
        painter.drawLine(int(cx), int(cy - size / 2), int(cx), int(cy + size / 2))

    def _draw_trace(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        if (
            self._trace_approach.isEmpty()
            and self._trace_release.isEmpty()
            and self._trace_follow.isEmpty()
        ):
            return

        approach_pen = self._segment_pen(QColor(60, 120, 200, 220))
        release_pen = self._segment_pen(QColor(243, 156, 18, 230))
        follow_pen = self._segment_pen(QColor(40, 160, 90, 230))

        # The polygons are in target-space mm. The painter does
        # the conversion to widget pixels in C++, which is much
        # cheaper than walking the trace in Python every paint.
        painter.save()
        # Antialiasing the trace stroke gets expensive once the
        # polyline has hundreds of vertices. The 3-pixel pen
        # weight hides any aliasing at video rate, so the trade
        # is invisible to the eye.
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(cx, cy)
        painter.scale(scale, scale)
        for polygon, pen in (
            (self._trace_approach, approach_pen),
            (self._trace_release, release_pen),
            (self._trace_follow, follow_pen),
        ):
            if not polygon.isEmpty():
                painter.setPen(pen)
                painter.drawPolyline(polygon)
        painter.restore()

    @staticmethod
    def _segment_pen(colour: QColor) -> QPen:
        pen = QPen(colour)
        pen.setWidth(3)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def _polygon_for_index(
        self,
        i: int,
        approach: QPolygonF,
        release: QPolygonF,
        follow: QPolygonF,
    ) -> QPolygonF:
        """Pick the polygon for the trace segment at sample ``i``.

        Falls back to the approach colour when no segmentation
        is in force, so a live trace reads as a single colour.
        The boundary sample itself belongs to the *new* segment
        so the visual transition lines up with the timestamp.
        """
        shot = self._shot_index
        release_idx = self._release_index
        if shot is not None and i > shot:
            return follow
        if release_idx is not None and i > release_idx:
            return release
        return approach

    def _draw_shots(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        # Render shots at the configured projectile diameter,
        # with a minimum pixel size so they remain visible at
        # very wide zoom levels.
        #
        # During replay (``_isolate_selected_shot``) only the
        # selected shot is drawn, and only once the playhead
        # has reached the shot's moment in the trace. That way
        # the marker appears at the same instant the shot fired
        # in real life rather than being painted over the trace
        # from the start of the window.
        diameter_px = max(4.0, self._shot_diameter_mm * scale)
        radius_px = diameter_px / 2.0
        for i, shot in enumerate(self._shots):
            if self._isolate_selected_shot:
                if i != self._selected_shot:
                    continue
                if not self._playhead_has_reached_shot():
                    continue
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
                painter.drawText(
                    QRectF(x + r + 4, y - 16, 30, 14), Qt.AlignmentFlag.AlignLeft, shot.label
                )

    def _playhead_has_reached_shot(self) -> bool:
        """Has the replay cursor arrived at (or past) the shot moment?

        In isolated replay the marker is suppressed until the
        playhead reaches the shot index, so the shot only shows
        up at the moment it actually happened. Outside isolated
        replay this method isn't called.

        Returns ``True`` when there's no shot index to gate on.
        That path doesn't apply during replay (the controller
        always sets a shot index when isolation is on) but the
        check keeps the helper safe for any future caller that
        doesn't.
        """
        if self._shot_index is None:
            return True
        if self._playhead_index is None:
            return False
        return self._playhead_index >= self._shot_index

    def _draw_live_aim(self, painter: QPainter, cx: float, cy: float, scale: float) -> None:
        if self._live_aim is None:
            return
        x = cx + self._live_aim[0] * scale
        y = cy + self._live_aim[1] * scale
        pen = QPen(QColor("#27ae60"))
        pen.setWidth(2)
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
