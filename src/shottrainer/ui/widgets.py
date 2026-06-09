"""Shared UI widget factories and helpers."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QWidget,
)


def make_expand_icon() -> QIcon:
    """Create the expand icon (four outward-pointing corners).

    Returns:
        A 18x18 QIcon suitable for overlay buttons on camera previews.
    """
    pm = QPixmap(18, 18)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(255, 255, 255, 220))
    pen.setWidth(2)
    p.setPen(pen)
    # Top-left corner
    p.drawLine(2, 6, 2, 2)
    p.drawLine(2, 2, 6, 2)
    # Top-right corner
    p.drawLine(11, 2, 15, 2)
    p.drawLine(15, 2, 15, 6)
    # Bottom-left corner
    p.drawLine(2, 11, 2, 15)
    p.drawLine(2, 15, 6, 15)
    # Bottom-right corner
    p.drawLine(11, 15, 15, 15)
    p.drawLine(15, 15, 15, 11)
    p.end()
    return QIcon(pm)


def make_expand_button(parent: QWidget) -> QPushButton:
    """Create a camera-preview expand button positioned for overlay use.

    The button is 26x26, uses a semi-transparent dark background, and
    carries the four-corner expand icon. The caller is responsible for
    positioning it (typically top-right of the camera container) and
    connecting its `clicked` signal.

    Args:
        parent: The widget the button will be parented to.

    Returns:
        A styled QPushButton ready for overlay placement.
    """
    btn = QPushButton(parent)
    btn.setFixedSize(26, 26)
    btn.setObjectName("expandButton")
    btn.setToolTip("Enlarge camera preview")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    icon = make_expand_icon()
    btn.setIcon(icon)
    btn.setIconSize(btn.size())
    return btn


ROTATION_OPTIONS: tuple[tuple[int, str], ...] = (
    (0, "None"),
    (90, "90 clockwise"),
    (180, "180"),
    (270, "90 counter-clockwise"),
)
"""Camera rotation presets as (degrees, display label) pairs."""

CALIBRES: tuple[tuple[str, str, float], ...] = (
    ("177", ".177 air pellet (4.5 mm)", 4.5),
    ("20", ".20 air pellet (5.0 mm)", 5.0),
    ("22", ".22 (5.6 mm)", 5.6),
    ("25", ".25 (6.35 mm)", 6.35),
    ("9mm", "9 mm", 9.0),
    ("45", ".45 (11.43 mm)", 11.43),
)
"""Calibre presets as (key, display label, diameter_mm) triples."""

CALIBRES_BY_KEY: dict[str, float] = {key: mm for key, _label, mm in CALIBRES}
"""Lookup from calibre key to its diameter in mm."""


def make_combo(
    items: list[tuple[object, str]] | list[tuple[str, str]] | list[tuple[int, str]],
    *,
    initial: object | None = None,
) -> QComboBox:
    """Build a QComboBox whose popup view sizes to its longest entry.

    Args:
        items: List of (data, display_label) pairs for the dropdown entries.
        initial: Data value to pre-select, matched via `findData`.

    Returns:
        A configured QComboBox with all items added.
    """
    combo = QComboBox()
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
    for value, label in items:
        combo.addItem(label, value)
    if initial is not None:
        idx = combo.findData(initial)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    metrics = combo.fontMetrics()
    max_w = max((metrics.horizontalAdvance(label) for _, label in items), default=120)
    combo.view().setMinimumWidth(max_w + 32)
    return combo


def add_field_with_hint(
    form: QFormLayout,
    label_text: str,
    field: QWidget,
    hint_text: str,
) -> None:
    """Add a form row with a field followed by a wrapped hint label.

    Args:
        form: The QFormLayout to add to.
        label_text: Row label (left column).
        field: The input widget for this row.
        hint_text: Explanatory text shown below the field.
    """
    form.addRow(label_text, field)
    hint = QLabel(hint_text)
    hint.setObjectName("formHint")
    hint.setWordWrap(True)
    hint.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
    form.addRow("", hint)


def section_label(text: str) -> QLabel:
    """Build a small uppercase heading for grouping fields in a tab.

    Args:
        text: The section title (will be uppercased automatically).

    Returns:
        A styled QLabel.
    """
    label = QLabel(text.upper())
    label.setObjectName("prefsSection")
    return label


class PropertySlider(QWidget):
    """A horizontal slider over a float range with a Reset button.

    Used for software image controls (brightness, contrast). The
    slider's integer position is mapped to the configured float range.
    ``value()`` returns the current float. The Reset button snaps back
    to ``default`` and announces the change so the live preview updates.
    """

    value_changed = Signal(str, object)  # property name, float

    def __init__(
        self,
        name: str,
        initial: float,
        *,
        minimum: float,
        maximum: float,
        default: float,
        steps: int = 200,
        suffix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """Initialise the slider widget.

        Args:
            name: Property name emitted with value changes.
            initial: Starting value.
            minimum: Lower bound of the float range.
            maximum: Upper bound of the float range.
            default: Value restored by the Reset button.
            steps: Number of discrete slider positions.
            suffix: Display suffix (e.g. 'x' for multipliers).
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._name = name
        self._minimum = minimum
        self._maximum = maximum
        self._default = default
        self._steps = steps
        self._suffix = suffix

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, steps)
        self._slider.setValue(self._float_to_pos(initial))
        layout.addWidget(self._slider, 1)

        self._readout = QLabel()
        self._readout.setMinimumWidth(56)
        self._readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._readout)

        self._reset = QPushButton("Reset")
        self._reset.setToolTip("Restore the default value")
        layout.addWidget(self._reset)

        self._slider.valueChanged.connect(self._on_slider_changed)
        self._reset.clicked.connect(self._on_reset_clicked)
        self._update_readout()

    def value(self) -> float:
        """Return the current slider value as a float."""
        return self._pos_to_float(self._slider.value())

    def set_value(self, value: float) -> None:
        """Move the slider to `value` without sending `value_changed`.

        Args:
            value: The new float value to display.
        """
        self._slider.blockSignals(True)
        try:
            self._slider.setValue(self._float_to_pos(value))
        finally:
            self._slider.blockSignals(False)
        self._update_readout()

    def _pos_to_float(self, pos: int) -> float:
        """Convert slider position to float value."""
        ratio = pos / self._steps
        return self._minimum + ratio * (self._maximum - self._minimum)

    def _float_to_pos(self, value: float) -> int:
        """Convert float value to slider position."""
        clamped = max(self._minimum, min(self._maximum, value))
        ratio = (clamped - self._minimum) / (self._maximum - self._minimum)
        return round(ratio * self._steps)

    def _update_readout(self) -> None:
        """Refresh the value label text."""
        value = self.value()
        if self._suffix:
            self._readout.setText(f"{value:.2f}")
        else:
            self._readout.setText(f"{value:+.0f}")

    def _on_slider_changed(self, _value: int) -> None:
        """Forward slider movement as a value_changed signal."""
        self._update_readout()
        self.value_changed.emit(self._name, self.value())

    def _on_reset_clicked(self) -> None:
        """Snap the slider back to its default value."""
        self._slider.setValue(self._float_to_pos(self._default))
