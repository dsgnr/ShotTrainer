"""Calibration dialog.

Two simple paths:

- automatic: the user shows the A4 sheet, the dialog displays the detected
  corners on the live preview and the user accepts.
- manual: the user clicks four points on the preview in order.

Detection itself is not done here. The dialog accepts a callback that runs
on demand. That keeps Qt out of the tracking package.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .camera_view import CameraView

DetectCornersFn = Callable[[np.ndarray], list[tuple[float, float]] | None]


class CalibrationDialog(QDialog):
    accepted_points = Signal(list)  # list[tuple[float, float]]

    def __init__(
        self,
        detect_corners: DetectCornersFn | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibrate target")
        self.resize(900, 600)

        self._detect_corners = detect_corners
        self._latest_frame: np.ndarray | None = None
        self._manual_points: list[tuple[float, float]] = []
        self._auto_points: list[tuple[float, float]] | None = None
        self._mode: str = "auto"

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Aim the rifle at an A4 sheet pinned at your target's position, "
            "in your normal shooting stance. Hold steady, then press Detect "
            "or click the four corners manually."
        )
        intro.setWordWrap(True)
        intro.setObjectName("calibrationIntro")
        layout.addWidget(intro)

        self._camera_view = CameraView()
        self._camera_view.clicked_at.connect(self._on_image_clicked)
        layout.addWidget(self._camera_view, 1)

        controls = QHBoxLayout()
        self._status = QLabel("Show the A4 sheet to the camera.")
        controls.addWidget(self._status, 1)

        self._auto_btn = QPushButton("Detect")
        self._manual_btn = QPushButton("Pick manually")
        self._reset_btn = QPushButton("Reset points")
        controls.addWidget(self._auto_btn)
        controls.addWidget(self._manual_btn)
        controls.addWidget(self._reset_btn)
        layout.addLayout(controls)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)

        self._auto_btn.clicked.connect(self._on_auto)
        self._manual_btn.clicked.connect(self._on_manual)
        self._reset_btn.clicked.connect(self._on_reset)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        self._latest_frame = frame_bgr
        self._camera_view.set_frame(frame_bgr)

    def _on_auto(self) -> None:
        if self._latest_frame is None or self._detect_corners is None:
            self._status.setText("No frame available for automatic detection.")
            return
        pts = self._detect_corners(self._latest_frame)
        if pts is None or len(pts) != 4:
            self._status.setText("Could not detect the sheet. Try manual selection.")
            self._auto_points = None
            return
        self._mode = "auto"
        self._auto_points = pts
        self._manual_points.clear()
        self._status.setText("Detected. Press OK to accept.")

    def _on_manual(self) -> None:
        self._mode = "manual"
        self._manual_points.clear()
        self._auto_points = None
        self._status.setText("Click the four corners: top-left, top-right, bottom-right, bottom-left.")

    def _on_reset(self) -> None:
        self._manual_points.clear()
        self._auto_points = None
        self._status.setText("Points cleared.")

    def _on_image_clicked(self, x: float, y: float) -> None:
        if self._mode != "manual":
            return
        if len(self._manual_points) >= 4:
            return
        self._manual_points.append((x, y))
        remaining = 4 - len(self._manual_points)
        if remaining:
            self._status.setText(f"{remaining} more point(s) to select.")
        else:
            self._status.setText("Four points captured. Press OK to accept.")

    def _on_accept(self) -> None:
        points: list[tuple[float, float]] | None
        if self._mode == "auto":
            points = self._auto_points
        else:
            points = self._manual_points if len(self._manual_points) == 4 else None
        if points is None:
            self._status.setText("No valid points to accept.")
            return
        self.accepted_points.emit(points)
        self.accept()
