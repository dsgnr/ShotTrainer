"""Compact panel showing per-session shot statistics."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QSizePolicy, QWidget

from shottrainer.services.shot_stats import (
    ShotStats,
    TraceStats,
    compute_stats,
    compute_trace_stats,
    time_inside_radius,
)

from .target_view import TargetRing


class StatsPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QFormLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setLabelAlignment(layout.labelAlignment())
        self._layout = layout

        self._count = QLabel("-")
        self._centre = QLabel("-")
        self._mean_radius = QLabel("-")
        self._spread = QLabel("-")
        self._tremor = QLabel("-")
        self._trace_length = QLabel("-")

        layout.addRow("Shots", self._count)
        layout.addRow("Group centre", self._centre)
        layout.addRow("Mean radius", self._mean_radius)
        layout.addRow("Extreme spread", self._spread)
        layout.addRow("Hold tremor", self._tremor)
        layout.addRow("Trace length", self._trace_length)

        # Time-in-ring rows are added dynamically once a ring set is known.
        self._ring_rows: list[tuple[QLabel, QLabel, TargetRing]] = []
        self._rings: tuple[TargetRing, ...] = ()
        self._last_trace: list[tuple[float, float]] | None = None

    def update_from_positions(self, positions: list[tuple[float, float]]) -> None:
        self.update_from_stats(compute_stats(positions))

    def update_from_stats(self, stats: ShotStats) -> None:
        self._count.setText(str(stats.count))
        if stats.count == 0:
            self._centre.setText("-")
            self._mean_radius.setText("-")
            self._spread.setText("-")
            return
        self._centre.setText(f"({stats.mean_x_mm:+.1f}, {stats.mean_y_mm:+.1f}) mm")
        self._mean_radius.setText(f"{stats.mean_radius_mm:.1f} mm")
        self._spread.setText(f"{stats.extreme_spread_mm:.1f} mm")

    def set_trace_stats(self, stats: TraceStats | None) -> None:
        if stats is None or stats.samples == 0:
            self._tremor.setText("-")
            self._trace_length.setText("-")
            return
        self._tremor.setText(f"{stats.hold_tremor_mm:.1f} mm RMS")
        self._trace_length.setText(f"{stats.trace_length_mm:.0f} mm")

    def set_trace_points(self, points: list[tuple[float, float]] | None) -> None:
        self._last_trace = list(points) if points else None
        if not points:
            self.set_trace_stats(None)
            self._refresh_time_in_ring(None)
            return
        self.set_trace_stats(compute_trace_stats(points))
        self._refresh_time_in_ring(list(points))

    def set_rings(self, rings: Sequence[TargetRing]) -> None:
        """Tell the panel which scoring rings to report time-in-ring for.

        Adds rows for the smallest ring (typically X/10) and a mid ring
        so the user can gauge precision and stability separately.
        """
        # Drop any existing rows.
        for label, _value, _ring in self._ring_rows:
            self._layout.removeRow(label)
        self._ring_rows.clear()
        self._rings = tuple(rings)

        chosen = self._select_diagnostic_rings(self._rings)
        for ring in chosen:
            label = QLabel(f"Time inside {ring.label or f'{ring.radius_mm:.0f} mm'}")
            value = QLabel("-")
            self._layout.addRow(label, value)
            self._ring_rows.append((label, value, ring))

        # Re-render with the current trace if there is one.
        self._refresh_time_in_ring(self._last_trace)

    def _select_diagnostic_rings(
        self, rings: Sequence[TargetRing]
    ) -> list[TargetRing]:
        if not rings:
            return []
        sorted_rings = sorted(rings, key=lambda r: r.radius_mm)
        if len(sorted_rings) == 1:
            return [sorted_rings[0]]
        return [sorted_rings[0], sorted_rings[len(sorted_rings) // 2]]

    def _refresh_time_in_ring(self, points: list[tuple[float, float]] | None) -> None:
        for _, value, ring in self._ring_rows:
            if not points:
                value.setText("-")
                continue
            fraction = time_inside_radius(points, ring.radius_mm)
            value.setText(f"{fraction * 100:.0f}%")
