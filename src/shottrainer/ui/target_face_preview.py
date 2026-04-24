"""Compact preview widget that draws a target face's rings."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .target_view import TargetRing


class TargetFacePreview(QWidget):
    """Square widget that renders a target face's rings centred and scaled to fit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the preview with no rings.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(160)
        self._rings: tuple[TargetRing, ...] = ()

    def set_rings(self, rings: Sequence[TargetRing]) -> None:
        """Set the rings to render.

        Args:
            rings: Sequence of `TargetRing` objects defining the face.
        """
        self._rings = tuple(rings)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#11161d"))

        if not self._rings:
            painter.setPen(QColor("#6b7180"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No face")
            return

        size = min(self.width(), self.height())
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        max_radius = max(r.diameter_mm for r in self._rings) / 2
        scale = (size - 16) / (2.0 * max_radius * 1.05)

        pen = QPen(QColor("#aab2c0"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for ring in self._rings:
            r = ring.diameter_mm / 2 * scale
            painter.drawEllipse(QPointF(cx, cy), r, r)
