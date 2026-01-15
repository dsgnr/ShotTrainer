"""Test setup. Runs Qt offscreen so UI tests don't need a display."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
