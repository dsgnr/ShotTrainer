"""Tests for the calibration watcher.

The watcher uses a QTimer. We drive it via ``force_check`` to avoid
sleeping in tests.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from shottrainer.app.calibration_store import save_calibration
from shottrainer.app.calibration_watcher import CalibrationWatcher
from shottrainer.tracking.calibration import LinearCalibration


def _bump_mtime(path: Path) -> None:
    """Ensure the file's mtime is strictly later than before."""
    now = time.time()
    os.utime(path, (now + 1, now + 1))


def test_no_change_when_file_missing(qtbot, tmp_path):
    watcher = CalibrationWatcher(path=tmp_path / "absent.json")
    received = []
    watcher.changed.connect(received.append)
    watcher.start()
    watcher.force_check()
    assert received == []


def test_emits_when_file_appears(qtbot, tmp_path):
    p = tmp_path / "calibration.json"
    watcher = CalibrationWatcher(path=p)
    received = []
    watcher.changed.connect(received.append)
    watcher.start()
    save_calibration(LinearCalibration(mm_per_pixel=0.5), p)
    watcher.force_check()
    assert len(received) == 1
    assert received[0] is not None


def test_no_emit_after_mark_seen(qtbot, tmp_path):
    p = tmp_path / "calibration.json"
    save_calibration(LinearCalibration(mm_per_pixel=0.5), p)
    watcher = CalibrationWatcher(path=p)
    received = []
    watcher.changed.connect(received.append)
    watcher.start()
    watcher.mark_seen()
    watcher.force_check()
    assert received == []


def test_emits_when_file_removed(qtbot, tmp_path):
    p = tmp_path / "calibration.json"
    save_calibration(LinearCalibration(mm_per_pixel=0.5), p)
    watcher = CalibrationWatcher(path=p)
    received = []
    watcher.changed.connect(received.append)
    watcher.start()
    p.unlink()
    watcher.force_check()
    assert received == [None]
