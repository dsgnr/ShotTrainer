"""Application theme.

A dark stylesheet that treats side panels as floating cards on a darker
canvas, with rounded corners and generous padding. The aim is to make
the app feel like a calm, modern instrument rather than a grid of
boxes.
"""

from __future__ import annotations

DARK_QSS = """
QWidget {
    background-color: #15181d;
    color: #e6e6e6;
    selection-background-color: #2d6cdf;
    selection-color: #ffffff;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #0f1217;
}

QSplitter {
    background-color: #0f1217;
}

QSplitter::handle {
    background: transparent;
    width: 6px;
    height: 6px;
}

/* Cards: any QFrame with card="true" floats on the canvas. */
QFrame[card="true"] {
    background-color: #181c22;
    border: 1px solid #232831;
    border-radius: 12px;
}

QLabel#cardTitle {
    font-size: 11px;
    letter-spacing: 1.4px;
    color: #6c7689;
    padding: 0 0 4px 0;
}

/* Main column wrappers stay invisible on the dark canvas. */
QFrame#leftColumn,
QFrame#centreColumn,
QFrame#rightColumn,
QFrame#columnCanvas {
    background-color: transparent;
    border: none;
}

QFrame#centreControls {
    background-color: #181c22;
    border: 1px solid #232831;
    border-radius: 12px;
}

/* Header bar */
QWidget#appHeader {
    background-color: #0f1217;
    border-bottom: 1px solid #1c2128;
}

QLabel#appHeaderTitle {
    font-size: 18px;
    font-weight: 600;
    color: #f6f7f8;
    letter-spacing: 0.5px;
}

QLabel#appHeaderStateLabel {
    font-size: 13px;
    color: #c8ccd4;
    letter-spacing: 0.4px;
}

QLabel#appHeaderCaption {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    color: #6c7689;
}

QLabel#appHeaderValue {
    font-size: 24px;
    font-weight: 600;
    color: #f6f7f8;
}

QToolButton#appHeaderSettings {
    border: none;
    border-radius: 20px;
    background-color: #1c2128;
    color: #cfd6e0;
    font-size: 18px;
}

QToolButton#appHeaderSettings:hover {
    background-color: #2d6cdf;
    color: #ffffff;
}

/* Status bar: thin and unobtrusive. */
QStatusBar {
    background-color: #0f1217;
    color: #8a93a4;
    border-top: 1px solid #1c2128;
}

QStatusBar::item {
    border: 0;
}

/* Menus */
QMenuBar {
    background-color: #0f1217;
    color: #d6dae3;
    padding: 2px 0;
}

QMenuBar::item {
    padding: 4px 10px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background-color: #1c2128;
}

QMenu {
    background-color: #181c22;
    border: 1px solid #232831;
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
    background-color: #232831;
    color: #f0f0f0;
    border: 1px solid #2d3340;
    border-radius: 6px;
    padding: 4px 8px;
}

/* Buttons: pill-shaped, generous padding. */
QPushButton {
    background-color: #232831;
    border: 1px solid #2d3340;
    border-radius: 8px;
    padding: 7px 14px;
    color: #e6e6e6;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #2d3340;
}

QPushButton:pressed {
    background-color: #1c2128;
}

QPushButton:disabled {
    background-color: #181c22;
    color: #57606e;
    border-color: #1f242c;
}

QPushButton:checked {
    background-color: #2d6cdf;
    border-color: #2d6cdf;
    color: #ffffff;
}

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0f1217;
    border: 1px solid #232831;
    border-radius: 8px;
    padding: 6px 10px;
    color: #e6e6e6;
    selection-background-color: #2d6cdf;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #2d6cdf;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #181c22;
    border: 1px solid #232831;
    border-radius: 6px;
    selection-background-color: #2d6cdf;
    padding: 4px;
}

/* Lists */
QListWidget, QListView, QTreeView, QTableView {
    background-color: transparent;
    border: none;
    outline: 0;
}

QListWidget::item, QListView::item {
    padding: 8px 10px;
    margin: 2px 0;
    border-radius: 6px;
    color: #d6dae3;
}

QListWidget::item:hover, QListView::item:hover {
    background-color: #1c2128;
}

QListWidget::item:selected, QListView::item:selected {
    background-color: #2d6cdf;
    color: #ffffff;
}

/* Tabs (preferences dialog) */
QTabWidget::pane {
    border: 1px solid #232831;
    background: #181c22;
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
    background: #1c2128;
    color: #f6f7f8;
}

QTabBar::tab:hover {
    color: #d6dae3;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 4px;
    background: #232831;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #2d6cdf;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #2d6cdf;
    border: 2px solid #15181d;
    width: 14px;
    height: 14px;
    margin: -7px 0;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    background: #4a8cf0;
}

/* Progress bars */
QProgressBar {
    background: #0f1217;
    border: 1px solid #232831;
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
    border: 1px solid #2d3340;
    border-radius: 4px;
    background: #0f1217;
}

QCheckBox::indicator:checked {
    background: #2d6cdf;
    border-color: #2d6cdf;
}

/* Header view (table headers) */
QHeaderView::section {
    background-color: #15181d;
    color: #8a93a4;
    border: none;
    border-bottom: 1px solid #232831;
    padding: 6px;
}

/* Scrollbars */
QScrollBar:vertical, QScrollBar:horizontal {
    background: transparent;
    border: none;
    width: 10px;
    height: 10px;
    margin: 2px;
}

QScrollBar::handle {
    background: #2d3340;
    border-radius: 4px;
    min-height: 30px;
    min-width: 30px;
}

QScrollBar::handle:hover {
    background: #3c4555;
}

QScrollBar::add-line, QScrollBar::sub-line {
    background: none;
    height: 0;
    width: 0;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
}

QLabel#calibrationIntro {
    color: #c8ccd4;
    font-size: 12px;
    padding: 4px 0 8px 0;
}
"""


def apply_dark_theme(app) -> None:
    """Apply the dark stylesheet to a QApplication."""
    app.setStyleSheet(DARK_QSS)
