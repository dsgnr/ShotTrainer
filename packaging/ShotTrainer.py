"""Entry script for the Nuitka build.

Nuitka derives the output directory and bundle name from the script's
filename, so this file is named ``ShotTrainer.py`` to produce
``dist/ShotTrainer.dist/`` (renamed to ``dist/ShotTrainer/`` after
the build) and ``dist/ShotTrainer.app`` on macOS.
"""

from shottrainer.app.main import main

if __name__ == "__main__":
    main()
