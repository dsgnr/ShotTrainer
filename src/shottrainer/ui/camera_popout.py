"""Pop-out camera preview dialog.

Double-click the camera preview in the main window to open a larger
view for focusing, framing and checking the image. The dialog receives
the same frames as the inline preview and closes with Escape or the
window close button.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from .camera_view import CameraView


class CameraPopout(QDialog):
    """A resizable dialog showing the camera preview at larger size.

    Double-click the camera preview in the main window to open this dialog.
    It receives the same frames as the inline preview and closes with
    Escape or the window close button.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the popout dialog.

        Args:
            parent: Optional parent widget for window ownership.
        """
        super().__init__(parent)
        self.setWindowTitle("Camera Preview")
        self.setMinimumSize(640, 480)
        self.resize(960, 720)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )

        self._view = CameraView()

        self._resolution_label = QLabel()
        self._resolution_label.setObjectName("cameraResolution")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view, 1)
        layout.addWidget(self._resolution_label)

        # Cmd+W (macOS) / Ctrl+W (other) closes the dialog.
        close_shortcut = QShortcut(QKeySequence.StandardKey.Close, self)
        close_shortcut.activated.connect(self.close)

    @property
    def view(self) -> CameraView:
        """The CameraView widget inside the dialog."""
        return self._view

    def set_resolution(self, width: int, height: int, fps: float = 0.0) -> None:
        """Update the resolution label shown below the preview.

        Args:
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Capture frame rate. Omitted from the label when zero.
        """
        text = f"{width} \u00d7 {height}"
        if fps > 0:
            text += f" @ {fps:.0f} fps"
        self._resolution_label.setText(text)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Close on Escape, delegate everything else to the base class."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
