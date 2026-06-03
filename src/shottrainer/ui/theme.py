"""Application theme."""

from __future__ import annotations

DARK_QSS = """
QWidget {
    background-color: #0e1014;
    color: #e6e6e6;
    selection-background-color: #2d6cdf;
    selection-color: #ffffff;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #0e1014;
}

QSplitter, QSplitter::handle {
    background-color: #0e1014;
}

QSplitter::handle {
    width: 0px;
    height: 0px;
}

QFrame#leftColumn {
    background-color: #0c0e12;
    border-right: 1px solid #181b21;
}

QFrame#centreColumn {
    background-color: #0e1014;
}

QFrame#rightColumn {
    background-color: #0c0e12;
    border-left: 1px solid #181b21;
}

/* Header */
QWidget#appHeader {
    background-color: #0a0c10;
    border-bottom: 1px solid #181b21;
}

QLabel#appHeaderTitle {
    font-size: 14px;
    font-weight: 600;
    color: #d6dae3;
    letter-spacing: 1px;
    text-transform: uppercase;
}

QLabel#appHeaderHint {
    color: #6c7689;
    font-size: 11px;
    letter-spacing: 0.5px;
}

QToolButton#appHeaderSettings {
    border: none;
    border-radius: 16px;
    background-color: transparent;
    color: #8a93a4;
    font-size: 18px;
}

QToolButton#appHeaderSettings:hover {
    background-color: #181b21;
    color: #ffffff;
}

/* Column captions */
QLabel#columnCaption {
    color: #5a6478;
    font-size: 10px;
    letter-spacing: 1.6px;
    text-transform: uppercase;
}

/* Inline hints under buttons in the left column. */
QLabel#inlineHint {
    color: #8a93a4;
    font-size: 11px;
    line-height: 1.3;
    padding: 0 0 4px 0;
}

/* Always-visible help text under a form field. */
QLabel#formHint {
    color: #8a93a4;
    font-size: 11px;
    line-height: 1.3;
    padding: 2px 0 6px 0;
}

/* Hero figures */
QLabel#heroValue {
    color: #f6f7f8;
    font-size: 30px;
    font-weight: 600;
    letter-spacing: -0.5px;
}

QLabel#heroCaption {
    color: #5a6478;
    font-size: 10px;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    padding-top: 2px;
}

QLabel#heroSubcaption {
    color: #6c7689;
    font-size: 10px;
    letter-spacing: 0.4px;
    padding-top: 1px;
    font-style: italic;
}

/* Shot list */
QListWidget#shotList {
    background-color: transparent;
    border: none;
    outline: 0;
}

QListWidget#shotList::item {
    background-color: transparent;
    margin: 0;
    padding: 0;
    border-radius: 8px;
}

QListWidget#shotList::item:hover {
    background-color: #14171c;
}

QListWidget#shotList::item:selected {
    background-color: #1c2128;
}

QLabel#shotRowNumber {
    color: #6c7689;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
}

QLabel#shotRowScore {
    color: #f6f7f8;
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.3px;
}

QLabel#shotRowOffset {
    color: #6c7689;
    font-size: 11px;
    letter-spacing: 0.3px;
}

QLabel#shotListEmpty,
QLabel#sessionListEmpty {
    color: #6c7689;
    font-size: 12px;
    line-height: 1.5;
    padding: 16px;
}

/* Status bar: thin and unobtrusive. */
QStatusBar {
    background-color: #0a0c10;
    color: #5a6478;
    border-top: 1px solid #181b21;
}

QStatusBar::item {
    border: 0;
}

/* Menus */
QMenuBar {
    background-color: #0a0c10;
    color: #d6dae3;
    padding: 2px 0;
}

QMenuBar::item {
    padding: 4px 10px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background-color: #181b21;
}

QMenu {
    background-color: #14171c;
    border: 1px solid #1f242c;
    border-radius: 8px;
    padding: 4px 0;
}

QMenu::item {
    padding: 6px 16px;
    border-radius: 4px;
    margin: 0 4px;
}

QMenu::item:selected {
    background-color: #2d6cdf;
}

QToolTip {
    background-color: #14171c;
    color: #f0f0f0;
    border: 1px solid #1f242c;
    border-radius: 6px;
    padding: 4px 8px;
}

/* Buttons */
QPushButton {
    background-color: #14171c;
    border: 1px solid #1f242c;
    border-radius: 8px;
    padding: 7px 14px;
    color: #d6dae3;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #1c2128;
}

QPushButton:pressed {
    background-color: #0c0e12;
}

QPushButton:disabled {
    background-color: #14171c;
    color: #4a5260;
    border-color: #181b21;
}

QPushButton:checked {
    background-color: #2d6cdf;
    border-color: #2d6cdf;
    color: #ffffff;
}

QPushButton#primaryButton {
    background-color: #2d6cdf;
    border-color: #2d6cdf;
    color: #ffffff;
    font-weight: 600;
    padding: 9px 14px;
}

QPushButton#primaryButton:hover {
    background-color: #4a8cf0;
    border-color: #4a8cf0;
}

QPushButton#primaryButton[variant="stop"] {
    background-color: #c0392b;
    border-color: #c0392b;
}

QPushButton#primaryButton[variant="stop"]:hover {
    background-color: #e64a3a;
    border-color: #e64a3a;
}

QLabel#sessionSummary {
    color: #6c7689;
    font-size: 11px;
    letter-spacing: 0.3px;
}

QLabel#aboutTitle {
    color: #f6f7f8;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

QLabel#zoomCaption {
    color: #6c7689;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

QLabel#zoomReadout {
    color: #d6dae3;
    font-size: 12px;
}

QPushButton#zoomButton {
    font-size: 16px;
    font-weight: 600;
    padding: 0;
    border-radius: 8px;
}

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0a0c10;
    border: 1px solid #1f242c;
    border-radius: 8px;
    padding: 6px 10px;
    color: #e6e6e6;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #2d6cdf;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #14171c;
    border: 1px solid #1f242c;
    border-radius: 6px;
    selection-background-color: #2d6cdf;
}

/* Lists (used in dialogs only now) */
QListWidget, QListView {
    background-color: transparent;
    border: none;
    outline: 0;
}

QListWidget::item, QListView::item {
    padding: 6px 10px;
    margin: 1px 0;
    border-radius: 6px;
}

QListWidget::item:selected, QListView::item:selected {
    background-color: #2d6cdf;
    color: #ffffff;
}

/* Tabs (preferences dialog) */
QTabWidget::pane {
    border: 1px solid #1f242c;
    background: #14171c;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background: transparent;
    color: #8a93a4;
    padding: 8px 18px;
    border: none;
    border-radius: 6px;
    margin: 2px 4px 2px 0;
}

QTabBar::tab:selected {
    background: #181b21;
    color: #f6f7f8;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 4px;
    background: #1f242c;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #2d6cdf;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #2d6cdf;
    border: 2px solid #0e1014;
    width: 14px;
    height: 14px;
    margin: -7px 0;
    border-radius: 9px;
}

/* Progress bars (used by audio meter behind the scenes) */
QProgressBar {
    background: #0a0c10;
    border: 1px solid #1f242c;
    border-radius: 8px;
    text-align: center;
    height: 8px;
}

QProgressBar::chunk {
    background-color: #2d6cdf;
    border-radius: 6px;
}

/* Checkboxes */
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #1f242c;
    border-radius: 4px;
    background: #0a0c10;
}

QCheckBox::indicator:checked {
    background: #2d6cdf;
    border-color: #2d6cdf;
    image: url("__CHECK_PATH__");
}

QCheckBox::indicator:disabled {
    border-color: #1f242c;
    background: #0c0e12;
}

QCheckBox:disabled {
    color: #4a5260;
}

QSlider:disabled::groove:horizontal {
    background: #181b21;
}

QSlider:disabled::sub-page:horizontal {
    background: #2d3340;
}

QSlider:disabled::handle:horizontal {
    background: #2d3340;
    border: 2px solid #0e1014;
}

/* Scrollbars */
QScrollBar:vertical, QScrollBar:horizontal {
    background: transparent;
    border: none;
    width: 8px;
    height: 8px;
    margin: 2px;
}

QScrollBar::handle {
    background: #1f242c;
    border-radius: 3px;
    min-height: 24px;
    min-width: 24px;
}

QScrollBar::handle:hover {
    background: #2d3340;
}

QScrollBar::add-line, QScrollBar::sub-line {
    background: none;
    height: 0;
    width: 0;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
}
"""


def apply_dark_theme(app) -> None:
    """Apply the dark stylesheet to a QApplication."""
    from .assets import asset_path

    # Use a forward-slash path so QSS parses it consistently on Windows.
    check_path = str(asset_path("check.svg")).replace("\\", "/")
    qss = DARK_QSS.replace("__CHECK_PATH__", check_path)
    app.setStyleSheet(qss)
