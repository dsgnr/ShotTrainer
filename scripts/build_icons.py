"""Regenerate PNG and Windows icons: python scripts/build_icons.py."""

import struct
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main() -> None:
    assets = Path(__file__).resolve().parents[1] / "src/shottrainer/ui/assets"
    renderer = QSvgRenderer(str(assets / "icon.svg"))
    if not renderer.isValid():
        raise ValueError("Invalid logo SVG")
    sizes = (16, 32, 48, 64, 128, 256, 512)
    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        if not image.save(str(assets / f"icon_{size}.png")):
            raise OSError(f"Could not save {size}px icon")

    # ICO supports embedded PNG images up to 256px (encoded as size 0).
    frames = [(size, (assets / f"icon_{size}.png").read_bytes()) for size in sizes[:-1]]
    directory = bytearray(struct.pack("<HHH", 0, 1, len(frames)))
    offset = 6 + 16 * len(frames)
    for size, data in frames:
        directory.extend(
            struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        )
        offset += len(data)
    (assets / "icon.ico").write_bytes(directory + b"".join(data for _, data in frames))


if __name__ == "__main__":
    main()
