"""Application theme.

A simple dark stylesheet covering the panels, dialogs and form controls.
The aim is to make the app look intentional rather than match a specific
design system. Light mode falls back to whatever the platform provides.
"""

from __future__ import annotations

DARK_QSS = """
QWidget {
    background-color: #1f2228;
    color: #e6e6e6;
    selection-background-color: #2d6cdf;
    selection-color: #ffffff;
}

QMainWindow, QDialog {
    background-color: #1a1d22;
}

QStatusBar {
    background-color: #15171b;
    color: #cfcfcf;
}

QStatusBar::item {
    border: 0;
}

QMenuBar {
    background-color: #15171b;
    color: #e6e6e6;
}

QMenuBar::item:selected {
    background-color: #2d6cdf;
}

QMenu {
    background-color: #1a1d22;
    border: 1px solid #2c303a;
}

QMenu::item:selected {
    background-color: #2d6cdf;
}

QToolTip {
    background-color: #2c303a;
    color: #f0f0f0;
    border: 1px solid #444;
}

QPushButton {
    background-color: #2c313c;
    border: 1px solid #3a4150;
    border-radius: 4px;
    padding: 6px 12px;
    color: #f0f0f0;
}

QPushButton:hover {
    background-color: #364056;
}

QPushButton:pressed {
    background-color: #1f2937;
}

QPushButton:disabled {
    background-color: #232730;
    color: #6b6f78;
    border-color: #2c303a;
}

QPushButton:checked {
    background-color: #2d6cdf;
    border-color: #2d6cdf;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #15171b;
    border: 1px solid #2c303a;
    border-radius: 3px;
    padding: 3px 6px;
    color: #f0f0f0;
}

QComboBox QAbstractItemView {
    background-color: #1a1d22;
    selection-background-color: #2d6cdf;
}

QListWidget, QListView, QTreeView, QTableView {
    background-color: #15171b;
    border: 1px solid #2c303a;
    alternate-background-color: #1a1d22;
}

QListWidget::item:selected, QListView::item:selected {
    background-color: #2d6cdf;
    color: #ffffff;
}

QTabWidget::pane {
    border: 1px solid #2c303a;
    background: #1f2228;
}

QTabBar::tab {
    background: #1a1d22;
    color: #c0c4cc;
    padding: 6px 14px;
    border: 1px solid #2c303a;
    border-bottom: none;
}

QTabBar::tab:selected {
    background: #2c313c;
    color: #ffffff;
}

QGroupBox, QFrame {
    border: 1px solid #2c303a;
    border-radius: 4px;
    margin-top: 6px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #2c303a;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #2d6cdf;
    border: none;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QProgressBar {
    background: #15171b;
    border: 1px solid #2c303a;
    border-radius: 3px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #2d6cdf;
    border-radius: 2px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3a4150;
    border-radius: 3px;
    background: #15171b;
}

QCheckBox::indicator:checked {
    background: #2d6cdf;
    border-color: #2d6cdf;
}

QSplitter::handle {
    background: #2c303a;
}

QHeaderView::section {
    background-color: #1a1d22;
    color: #c0c4cc;
    border: 1px solid #2c303a;
    padding: 4px;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background: #1a1d22;
    border: none;
}

QScrollBar::handle {
    background: #3a4150;
    border-radius: 3px;
}

QScrollBar::handle:hover {
    background: #4a5160;
}

QScrollBar::add-line, QScrollBar::sub-line {
    background: none;
}

QLabel#calibrationIntro {
    color: #c8ccd4;
    font-size: 12px;
    padding: 4px 0 8px 0;
}
"""


def apply_dark_theme(app) -> None:  # noqa: ANN001 (Qt type comes from runtime)
    """Apply the dark stylesheet to a QApplication."""
    app.setStyleSheet(DARK_QSS)
