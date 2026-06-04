"""The big headline figures shown down the right column.

Three numbers. Shot count, group size, hold tremor. Each shows
up as a big number with a small caption underneath. Replaces
the form-style stats panel in the new layout, but the underlying
calculation still comes from the shot-stats service via
:meth:`update_from_positions` and the trace via
:meth:`set_trace_points`.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from shottrainer.app.target_faces import TargetRing, diagnostic_rings
from shottrainer.services.scoring import total_score
from shottrainer.services.shot_stats import (
    ShotStats,
    TraceStats,
    compute_stats,
    compute_trace_stats,
    time_inside_radius,
)


class _HeroFigure(QWidget):
    def __init__(
        self,
        caption: str,
        *,
        subcaption: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.value = QLabel("-")
        self.value.setObjectName("heroValue")
        self.value.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.caption = QLabel(caption.upper())
        self.caption.setObjectName("heroCaption")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.value)
        layout.addWidget(self.caption)
        self.subcaption: QLabel | None = None
        if subcaption is not None:
            self.subcaption = QLabel(subcaption)
            self.subcaption.setObjectName("heroSubcaption")
            self.subcaption.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self.subcaption)


class HeroStats(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        self._total = _HeroFigure("Total score")
        self._group = _HeroFigure("Group size", subcaption="extreme spread")
        self._tremor = _HeroFigure("Hold tremor", subcaption="RMS deviation")
        self._inner = _HeroFigure("Time on target")
        layout.addWidget(self._total)
        layout.addWidget(self._group)
        layout.addWidget(self._tremor)
        layout.addWidget(self._inner)

        self._rings: tuple[TargetRing, ...] = ()
        self._scores: list[str] = []
        self._last_trace: list[tuple[float, float]] | None = None

    def update_from_positions(self, positions: list[tuple[float, float]]) -> None:
        self.update_from_stats(compute_stats(positions))

    def update_from_stats(self, stats: ShotStats) -> None:
        if stats.count == 0:
            self._group.value.setText("-")
            self._group.value.setToolTip("")
            return
        # Extreme spread is the most relatable group measure for shooters.
        # Mean radius is the more typical statistical measure of grouping.
        # Show it on the tooltip so the alternative is one hover away.
        self._group.value.setText(f"{stats.extreme_spread_mm:.1f}\u202fmm")
        self._group.value.setToolTip(
            f"Extreme spread: {stats.extreme_spread_mm:.1f} mm\n"
            f"Mean radius from group centre: {stats.mean_radius_mm:.1f} mm"
        )

    def set_scores(self, scores: list[str]) -> None:
        """Set the per-shot scores. Recomputes the total."""
        self._scores = list(scores)
        if not self._scores:
            self._total.value.setText("-")
            return
        total = total_score(self._scores)
        if total <= 0:
            # Nothing parsed, or all misses. Show shot count instead.
            self._total.value.setText(f"{len(self._scores)} shots")
            return
        self._total.value.setText(f"{total:g}")

    def set_trace_stats(self, stats: TraceStats | None) -> None:
        if stats is None or stats.samples == 0:
            self._tremor.value.setText("-")
            return
        self._tremor.value.setText(f"{stats.hold_tremor_mm:.1f}\u202fmm")

    def set_rings(self, rings: Sequence[TargetRing]) -> None:
        self._rings = tuple(rings)
        self._refresh_inner_caption()
        self._refresh_inner_value()

    def set_trace_points(self, points: list[tuple[float, float]] | None) -> None:
        self._last_trace = list(points) if points else None
        if not points:
            self.set_trace_stats(None)
            self._inner.value.setText("-")
            return
        self.set_trace_stats(compute_trace_stats(points))
        self._refresh_inner_value()

    def _refresh_inner_caption(self) -> None:
        chosen = diagnostic_rings(self._rings)
        if chosen:
            ring = chosen[0]
            label = ring.label or f"{ring.diameter_mm:.0f}\u202fmm"
            self._inner.caption.setText(f"TIME INSIDE {label}")
        else:
            self._inner.caption.setText("TIME ON TARGET")

    def _refresh_inner_value(self) -> None:
        if not self._last_trace:
            self._inner.value.setText("-")
            return
        chosen = diagnostic_rings(self._rings)
        if not chosen:
            self._inner.value.setText("-")
            return
        fraction = time_inside_radius(self._last_trace, chosen[0].diameter_mm / 2)
        self._inner.value.setText(f"{fraction * 100:.0f}%")
