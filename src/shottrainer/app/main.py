"""Where the app starts."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from shottrainer import __version__


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

    # The main window is set up below. Wiring of camera and audio
    # services happens once the user starts a session.
    from shottrainer.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
