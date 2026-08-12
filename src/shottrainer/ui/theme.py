"""Application theme."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg: str = "#0e1014"
    bg_dark: str = "#0a0c10"
    bg_panel: str = "#14171c"
    bg_panel_2: str = "#181b21"
    bg_panel_3: str = "#1c2128"
    bg_border: str = "#1f242c"

    text: str = "#e6e6e6"
    text_heading: str = "#d6dae3"
    text_muted: str = "#8a93a4"
    text_dim: str = "#6c7689"
    text_soft: str = "#5a6478"
    text_disabled: str = "#4a5260"
    text_bright: str = "#f6f7f8"
    white: str = "#ffffff"

    accent: str = "#2d6cdf"
    accent_hover: str = "#4a8cf0"
    danger: str = "#c0392b"
    danger_hover: str = "#e64a3a"


_DEFAULT_PALETTE = Palette()


def build_stylesheet(check_path: str = "__CHECK_PATH__", p: Palette = _DEFAULT_PALETTE) -> str:
    """Generate the application-wide QSS stylesheet.

    Args:
        check_path: File path to the checkbox check icon SVG.
        p: Colour palette to use for all tokens.

    Returns:
        A complete QSS string ready for `QApplication.setStyleSheet`.
    """
    return f"""
QWidget {{
    background-color: {p.bg};
    color: {p.text};
    selection-background-color: {p.accent};
    selection-color: {p.white};
    font-size: 13px;
}}

QSplitter {{
    border-top: 1px solid {p.bg_panel_2};
}}

QSplitter::handle {{
    background: {p.bg};
    width: 0px;
    height: 0px;
}}

QSplitter::handle:horizontal {{
    background: {p.bg};
    width: 0px;
}}

QSplitter::handle:vertical {{
    background: {p.bg};
    height: 0px;
}}

QFrame#leftColumn {{
    border-right: 1px solid {p.bg_panel_2};
}}

QFrame#rightColumn {{
    border-left: 1px solid {p.bg_panel_2};
}}

/* Header */
QLabel#appHeaderTitle {{
    color: {p.text_heading};
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}}

QLabel#appHeaderHint,
QLabel#columnCaption,
QLabel#sessionSummary,
QLabel#zoomCaption,
QLabel#heroCaption,
QLabel#heroSubcaption,
QLabel#shotRowNumber,
QLabel#shotRowOffset,
QLabel#inlineHint,
QLabel#formHint,
QLabel#shotListEmpty,
QLabel#sessionListEmpty,
QLabel#zoomReadout {{
    color: {p.text_dim};
}}

/* Labels in general are transparent so list-row hover and selection
backgrounds aren't broken up by the QWidget palette fill. */
QLabel {{
    background: transparent;
}}

/* Same for the row container widgets used inside QListWidget. The
list itself paints the hover and selection backgrounds, the row's
own widget has to stay transparent so they show through. */
QWidget#shotRow,
QWidget#sessionRow {{
    background: transparent;
    border-radius: 6px;
}}

QWidget#shotRow:hover,
QWidget#sessionRow:hover {{
    background: {p.bg_panel};
}}

QLabel#appHeaderHint {{
    font-size: 11px;
    letter-spacing: 0.5px;
}}

QToolButton#appHeaderSettings {{
    border: none;
    border-radius: 16px;
    background: transparent;
    color: {p.text_muted};
    font-size: 18px;
}}

QToolButton#appHeaderSettings:hover {{
    background-color: {p.bg_panel_2};
    color: {p.white};
}}

/* Text blocks */
QLabel#columnCaption,
QLabel#heroCaption,
QLabel#zoomCaption {{
    background: transparent;
    font-size: 10px;
    letter-spacing: 1.6px;
    text-transform: uppercase;
}}

QLabel#inlineHint,
QLabel#formHint,
QLabel#shotListEmpty,
QLabel#sessionListEmpty {{
    font-size: 11px;
    line-height: 1.3;
}}

QLabel#inlineHint {{
    padding: 0 0 4px 0;
}}

QLabel#formHint {{
    padding: 2px 0 6px 0;
}}

QLabel#heroValue {{
    background: transparent;
    color: {p.text_bright};
    font-size: 30px;
    font-weight: 600;
    letter-spacing: -0.5px;
}}

QLabel#heroSubcaption {{
    background: transparent;
    font-size: 10px;
    letter-spacing: 0.4px;
    padding-top: 1px;
    font-style: italic;
}}

QLabel#aboutTitle {{
    color: {p.text_bright};
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

QLabel#aboutMeta {{
    background: transparent;
    color: {p.text_dim};
    font-size: 11px;
    letter-spacing: 0.3px;
    padding-bottom: 8px;
}}

QLabel#prefsSection {{
    background: transparent;
    color: {p.text_dim};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    padding: 4px 0 2px 0;
    border-bottom: 1px solid {p.bg_border};
    margin-bottom: 4px;
}}

/* Session browser rows */
QLabel#sessionRowTitle {{
    background: transparent;
    color: {p.text_bright};
    font-size: 13px;
    font-weight: 600;
    letter-spacing: -0.1px;
}}

QLabel#sessionRowMeta {{
    background: transparent;
    color: {p.text_dim};
    font-size: 11px;
    letter-spacing: 0.2px;
}}

QLabel#sessionRowScore {{
    background: transparent;
    color: {p.text_bright};
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.2px;
    padding-left: 12px;
}}

/* Lists */
QListWidget#shotList,
QListWidget#sessionList,
QListWidget,
QListView {{
    background: transparent;
    border: none;
    outline: 0;
}}

QListWidget#shotList::item,
QListWidget#sessionList::item,
QListWidget::item,
QListView::item {{
    background: transparent;
    margin: 0;
    padding: 0;
    border-radius: 8px;
}}

QListWidget#shotList::item:hover,
QListWidget#sessionList::item:hover {{
    background-color: {p.bg_panel};
}}

QListWidget#shotList::item:selected,
QListWidget#sessionList::item:selected {{
    background-color: {p.bg_panel_2};
}}

QListWidget::item,
QListView::item {{
    padding: 6px 10px;
    margin: 1px 0;
    border-radius: 6px;
}}

QListWidget::item:selected,
QListView::item:selected {{
    background-color: {p.accent};
    color: {p.white};
}}

/* Status bar */
QStatusBar {{
    background-color: {p.bg_dark};
    color: {p.text_soft};
    border-top: 1px solid {p.bg_panel_2};
}}

QStatusBar::item {{
    border: 0;
}}

/* Menus */
QMenuBar {{
    background-color: {p.bg_dark};
    color: {p.text_heading};
    padding: 2px 0;
}}

QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 6px;
}}

QMenuBar::item:selected {{
    background-color: {p.bg_panel_2};
}}

QMenu {{
    background-color: {p.bg_panel};
    border: 1px solid {p.bg_border};
    border-radius: 8px;
    padding: 4px 0;
}}

QMenu::item {{
    padding: 6px 16px;
    border-radius: 4px;
    margin: 0 4px;
}}

QMenu::item:selected {{
    background-color: {p.accent};
}}

QToolTip {{
    background-color: {p.bg_panel};
    color: {p.text_bright};
    border: 1px solid {p.bg_border};
    border-radius: 6px;
    padding: 4px 8px;
}}

/* Buttons */
QPushButton,
QToolButton {{
    background-color: {p.bg_panel};
    border: 1px solid {p.bg_border};
    border-radius: 8px;
    color: {p.text_heading};
}}

QPushButton {{
    padding: 7px 14px;
    min-height: 18px;
}}

QPushButton:hover,
QToolButton:hover {{
    background-color: {p.bg_panel_3};
}}

QPushButton:pressed,
QToolButton:pressed {{
    background-color: #0c0e12;
}}

QPushButton:disabled,
QToolButton:disabled {{
    background-color: {p.bg_panel};
    color: {p.text_disabled};
    border-color: {p.bg_panel_2};
}}

QPushButton:checked {{
    background-color: {p.accent};
    border-color: {p.accent};
    color: {p.white};
}}

QPushButton#primaryButton {{
    background-color: {p.accent};
    border-color: {p.accent};
    color: {p.white};
    font-weight: 600;
    padding: 9px 14px;
}}

QPushButton#primaryButton:hover {{
    background-color: {p.accent_hover};
    border-color: {p.accent_hover};
}}

QPushButton#primaryButton[variant="stop"] {{
    background-color: {p.danger};
    border-color: {p.danger};
}}

QPushButton#primaryButton[variant="stop"]:hover {{
    background-color: {p.danger_hover};
    border-color: {p.danger_hover};
}}

QPushButton#zoomButton {{
    font-size: 16px;
    font-weight: 600;
    padding: 0;
    border-radius: 8px;
}}

QPushButton#expandButton {{
    background: rgba(0, 0, 0, 160);
    border: none;
    border-radius: 4px;
    padding: 4px;
}}

QPushButton#expandButton:hover {{
    background: rgba(60, 60, 60, 200);
}}

QLabel#cameraResolution {{
    color: {p.text_dim};
    font-size: 11px;
    padding: 4px 8px;
}}

QLabel#detectorStatus {{
    color: {p.text_dim};
}}

QLabel#statePill {{
    border: 1px solid {p.text_dim};
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {p.bg_dark};
    border: 1px solid {p.bg_border};
    border-radius: 8px;
    padding: 6px 10px;
    color: {p.text};
}}

QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus,
QTextEdit:focus,
QPlainTextEdit:focus {{
    border: 1px solid {p.accent};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {p.bg_panel};
    border: 1px solid {p.bg_border};
    border-radius: 6px;
    selection-background-color: {p.accent};
}}

/* Tabs */
QTabWidget::pane {{
    border: 1px solid {p.bg_border};
    background: {p.bg_panel};
    border-radius: 8px;
    top: -1px;
}}

QTabBar::tab {{
    background: transparent;
    color: {p.text_muted};
    padding: 8px 18px;
    border: none;
    border-radius: 6px;
    margin: 2px 4px 2px 0;
}}

QTabBar::tab:selected {{
    background: {p.bg_panel_2};
    color: {p.text_bright};
}}

/* Slider */
QSlider {{
    background: transparent;
    border: none;
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: {p.bg_border};
    border: none;
    border-radius: 3px;
    margin: 4px 0;
}}

QSlider::sub-page:horizontal {{
    background: {p.accent};
    border-radius: 3px;
    margin: 4px 0;
}}

QSlider::add-page:horizontal {{
    background: {p.bg_border};
    border-radius: 3px;
    margin: 4px 0;
}}

QSlider::handle:horizontal {{
    background: {p.accent};
    border: 2px solid {p.bg};
    width: 14px;
    height: 14px;
    margin: -7px 0;
    border-radius: 9px;
}}

/* Progress */
QProgressBar {{
    background: {p.bg_dark};
    border: 1px solid {p.bg_border};
    border-radius: 8px;
    text-align: center;
    height: 8px;
}}

QProgressBar::chunk {{
    background-color: {p.accent};
    border-radius: 6px;
}}

/* Checkbox */
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {p.bg_border};
    border-radius: 4px;
    background: {p.bg_dark};
}}

QCheckBox::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
    image: url("{check_path}");
}}

QCheckBox::indicator:disabled {{
    border-color: {p.bg_border};
    background: #0c0e12;
}}

QCheckBox:disabled {{
    color: {p.text_disabled};
}}

/* Scrollbars */
QScrollBar:vertical,
QScrollBar:horizontal {{
    background: transparent;
    border: none;
    width: 8px;
    height: 8px;
    margin: 2px;
}}

QScrollBar::handle {{
    background: {p.bg_border};
    border-radius: 3px;
    min-height: 24px;
    min-width: 24px;
}}

QScrollBar::handle:hover {{
    background: #2d3340;
}}

QScrollBar::add-line,
QScrollBar::sub-line {{
    background: none;
    height: 0;
    width: 0;
}}

QScrollBar::add-page,
QScrollBar::sub-page {{
    background: none;
}}
""".strip()


def apply_dark_theme(app) -> None:
    """Apply the dark stylesheet to a QApplication."""
    from .assets import asset_path

    check_path = str(asset_path("check.svg")).replace("\\", "/")
    app.setStyleSheet(build_stylesheet(check_path=check_path))

    # Qt has no stylesheet or style-hint mechanism for setting cursors
    # on widget classes. An app-level event filter on Polish is the
    # standard workaround.
    from PySide6.QtCore import QEvent, QObject, Qt
    from PySide6.QtWidgets import QPushButton, QToolButton

    class _ButtonCursorFilter(QObject):
        def eventFilter(self, obj, event):  # noqa: N802
            if event.type() == QEvent.Type.Polish and isinstance(obj, (QPushButton, QToolButton)):
                obj.setCursor(Qt.CursorShape.PointingHandCursor)
            return False

    app._button_cursor_filter = _ButtonCursorFilter(app)
    app.installEventFilter(app._button_cursor_filter)
