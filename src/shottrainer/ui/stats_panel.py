"""Compact panel showing per-session shot statistics."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QSizePolicy, QWidget

from shottrainer.services.shot_stats import ShotStats, compute_stats


class StatsPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QFormLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setLabelAlignment(layout.labelAlignment())

        self._count = QLabel("-")
        self._centre = QLabel("-")
        self._mean_radius = QLabel("-")
        self._spread = QLabel("-")

        layout.addRow("Shots", self._count)
        layout.addRow("Group centre", self._centre)
        layout.addRow("Mean radius", self._mean_radius)
        layout.addRow("Extreme spread", self._spread)

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
