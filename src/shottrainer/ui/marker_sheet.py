"""Generate and print a calibration marker sheet.

A4 page with a centred black circle. The diameter is settable
so users can match the size to their target stand. The dialog
can save to PDF or hand off to the system print dialog.
"""

from __future__ import annotations

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0


class MarkerSheetDialog(QDialog):
    def __init__(
        self,
        diameter_mm: float = 60.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Print marker sheet")
        self.resize(360, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._diameter = QDoubleSpinBox()
        self._diameter.setRange(5.0, 1000.0)
        self._diameter.setSingleStep(1.0)
        self._diameter.setSuffix(" mm")
        self._diameter.setValue(float(diameter_mm))
        form.addRow("Circle diameter", self._diameter)
        layout.addLayout(form)

        self._save_pdf = QPushButton("Save PDF...")
        self._save_pdf.clicked.connect(self._on_save_pdf)
        layout.addWidget(self._save_pdf)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        print_btn = buttons.addButton("Print...", QDialogButtonBox.ButtonRole.AcceptRole)
        print_btn.clicked.connect(self._on_print)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def diameter_mm(self) -> float:
        return float(self._diameter.value())

    def _on_save_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save marker sheet", "marker.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        self._configure_printer(printer)
        self._render(printer)

    def _on_print(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self._configure_printer(printer)
        if QPrintDialog(printer, self).exec() == QDialog.DialogCode.Accepted:
            self._render(printer)

    def _configure_printer(self, printer: QPrinter) -> None:
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)

    def _render(self, printer: QPrinter) -> None:
        painter = QPainter(printer)
        try:
            page_rect = printer.pageRect(QPrinter.Unit.Millimeter)
            # Map the page in mm to the printer device in pixels.
            painter.setWindow(0, 0, int(page_rect.width()), int(page_rect.height()))

            cx = page_rect.width() / 2.0
            cy = page_rect.height() / 2.0

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#000000"))
            r = self._diameter.value() / 2.0
            painter.drawEllipse(QPointF(cx, cy), r, r)

            painter.setPen(QColor("#000000"))
            label = f"ShotTrainer marker  -  {self._diameter.value():.0f} mm"
            painter.drawText(
                QRectF(0, page_rect.height() - 12, page_rect.width(), 10),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                label,
            )
        finally:
            painter.end()
