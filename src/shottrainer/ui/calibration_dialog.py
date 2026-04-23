"""Calibration dialog.

The user enters the printed calibration circle's diameter, the dialog
locates the circle in the live preview, and on accept the centre and
radius are emitted along with the diameter. The fit is performed
elsewhere (``CalibrationController``). This dialog only collects the
geometry.

Two paths are supported:

- automatic: press *Detect* to run the supplied circle finder on the
  current frame.
- manual: press *Pick manually*, click the circle's centre, then click
  any point on its edge. The radius comes from the distance between
  those two clicks.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .camera_view import CameraView

DetectCircleFn = Callable[[np.ndarray], tuple[float, float, float] | None]


class _CalibrationCameraView(CameraView):
    """Camera preview with an extra overlay for the candidate circle.

    The base view already draws the live aim overlay. We add a separate
    cyan circle to show the calibration candidate without colliding with
    the green aim cross.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._candidate: tuple[float, float, float] | None = None

    def set_candidate(self, circle: tuple[float, float, float] | None) -> None:
        self._candidate = circle
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().paintEvent(event)
        if self._candidate is None or self._pixmap is None:
            return
        fw, fh = self._frame_size
        if fw == 0 or fh == 0:
            return
        target = self.rect()
        scaled = self._pixmap.size().scaled(target.size(), Qt.AspectRatioMode.KeepAspectRatio)
        sw, sh = scaled.width(), scaled.height()
        ox = (target.width() - sw) // 2
        oy = (target.height() - sh) // 2

        cx_px, cy_px, r_px = self._candidate
        sx = ox + cx_px * sw / fw
        sy = oy + cy_px * sh / fh
        radius = max(4.0, r_px * sw / fw)

        painter = QPainter(self)
        try:
            pen = QPen(QColor("#22d3ee"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 0, 0, 0))
            painter.drawEllipse(
                int(sx - radius),
                int(sy - radius),
                int(radius * 2),
                int(radius * 2),
            )
            # Small cross at the centre.
            painter.drawLine(int(sx - 6), int(sy), int(sx + 6), int(sy))
            painter.drawLine(int(sx), int(sy - 6), int(sx), int(sy + 6))
        finally:
            painter.end()


class CalibrationDialog(QDialog):
    accepted_circle = Signal(float, float, float, float)  # cx_px, cy_px, r_px, diameter_mm

    def __init__(
        self,
        detect_circle: DetectCircleFn | None = None,
        diameter_mm: float = 60.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibrate target")
        self.resize(900, 620)

        self._detect_circle = detect_circle
        self._latest_frame: np.ndarray | None = None
        self._candidate: tuple[float, float, float] | None = None
        self._mode: str = "auto"
        self._manual_centre: tuple[float, float] | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Print the marker sheet (Tools > Print marker sheet), pin it "
            "where the target will be and aim at it from your shooting "
            "stance. Enter the printed circle diameter, then press Detect "
            "or pick the circle manually."
        )
        intro.setWordWrap(True)
        intro.setObjectName("calibrationIntro")
        layout.addWidget(intro)

        form = QFormLayout()
        self._diameter = QDoubleSpinBox()
        self._diameter.setRange(5.0, 200.0)
        self._diameter.setSingleStep(1.0)
        self._diameter.setSuffix(" mm")
        self._diameter.setValue(float(diameter_mm))
        self._diameter.setToolTip(
            "Diameter of the printed calibration circle. Match the value "
            "you used in the marker sheet dialog."
        )
        form.addRow("Circle diameter", self._diameter)
        layout.addLayout(form)

        self._camera_view = _CalibrationCameraView()
        self._camera_view.clicked_at.connect(self._on_image_clicked)
        layout.addWidget(self._camera_view, 1)

        controls = QHBoxLayout()
        self._status = QLabel("Show the marker sheet to the camera.")
        controls.addWidget(self._status, 1)

        self._auto_btn = QPushButton("Detect")
        self._manual_btn = QPushButton("Pick manually")
        self._reset_btn = QPushButton("Reset")
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
        if self._latest_frame is None or self._detect_circle is None:
            self._status.setText("No frame available for automatic detection.")
            return
        result = self._detect_circle(self._latest_frame)
        if result is None:
            self._status.setText("Could not find a circle. Try manual selection.")
            self._candidate = None
            self._camera_view.set_candidate(None)
            return
        self._mode = "auto"
        self._candidate = result
        self._manual_centre = None
        self._camera_view.set_candidate(result)
        self._status.setText(f"Detected circle (radius {result[2]:.1f} px). Press OK to accept.")

    def _on_manual(self) -> None:
        self._mode = "manual"
        self._candidate = None
        self._manual_centre = None
        self._camera_view.set_candidate(None)
        self._status.setText("Click the circle's centre.")

    def _on_reset(self) -> None:
        self._candidate = None
        self._manual_centre = None
        self._camera_view.set_candidate(None)
        self._status.setText("Selection cleared.")

    def _on_image_clicked(self, x: float, y: float) -> None:
        if self._mode != "manual":
            return
        if self._manual_centre is None:
            self._manual_centre = (x, y)
            self._status.setText("Now click any point on the circle's edge.")
            return
        cx, cy = self._manual_centre
        radius = float(np.hypot(x - cx, y - cy))
        if radius < 1.0:
            self._status.setText("Edge click was too close to the centre. Try again.")
            return
        self._candidate = (cx, cy, radius)
        self._camera_view.set_candidate(self._candidate)
        self._status.setText(
            f"Manual circle captured (radius {radius:.1f} px). Press OK to accept."
        )

    def _on_accept(self) -> None:
        if self._candidate is None:
            self._status.setText("No circle selected.")
            return
        cx, cy, r = self._candidate
        self.accepted_circle.emit(float(cx), float(cy), float(r), float(self._diameter.value()))
        self.accept()

    def diameter_mm(self) -> float:
        return float(self._diameter.value())
