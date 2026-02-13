"""Where the app starts."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from shottrainer import __version__

from .controller import AppController
from .paths import database_path


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

    from shottrainer.ui.main_window import MainWindow

    window = MainWindow()
    controller = AppController(window, database_path())
    app.aboutToQuit.connect(controller.shutdown)

    window.show()
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
