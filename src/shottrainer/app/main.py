"""Where the app starts."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from shottrainer import __version__
from shottrainer.ui.assets import asset_path
from shottrainer.ui.theme import apply_dark_theme

from .controller import AppController
from .paths import database_path
from .ui_state import (
    UiState,
    decode_geometry,
    encode_geometry,
    load_ui_state,
    save_ui_state,
)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("shottrainer")
    log.info("ShotTrainer %s starting", __version__)

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("ShotTrainer")
    app.setOrganizationName("ShotTrainer")

    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256, 512):
        icon.addFile(str(asset_path(f"icon_{size}.png")))
    app.setWindowIcon(icon)

    apply_dark_theme(app)

    from shottrainer.ui.main_window import MainWindow

    window = MainWindow()
    controller = AppController(window, database_path())

    state = load_ui_state()
    geometry = decode_geometry(state.window_geometry_b64)
    if geometry:
        window.restoreGeometry(QByteArray(geometry))
    window.restore_main_splitter_sizes(state.main_splitter_sizes)

    def _persist_state() -> None:
        try:
            save_ui_state(
                UiState(
                    window_geometry_b64=encode_geometry(bytes(window.saveGeometry())),
                    main_splitter_sizes=window.main_splitter_sizes(),
                )
            )
        except OSError as exc:
            log.warning("Could not save UI state: %s", exc)

    app.aboutToQuit.connect(_persist_state)
    app.aboutToQuit.connect(controller.shutdown)

    window.show()
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
