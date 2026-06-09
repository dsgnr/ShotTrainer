"""Tests for the shared UI widget helpers in shottrainer.ui.widgets."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QFormLayout, QWidget

from shottrainer.ui.widgets import (
    CALIBRES,
    CALIBRES_BY_KEY,
    ROTATION_OPTIONS,
    PropertySlider,
    add_field_with_hint,
    make_combo,
    make_expand_button,
    make_expand_icon,
    section_label,
)


def test_make_expand_icon_returns_valid_icon(qtbot):
    icon = make_expand_icon()
    assert not icon.isNull()


def test_make_expand_button_creates_styled_button(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    btn = make_expand_button(parent)
    assert btn.parent() is parent
    assert btn.width() == 26
    assert btn.height() == 26
    assert not btn.icon().isNull()
    assert btn.toolTip() == "Enlarge camera preview"


def test_make_combo_selects_initial(qtbot):
    items = [(0, "Zero"), (1, "One"), (2, "Two")]
    combo = make_combo(items, initial=2)
    qtbot.addWidget(combo)
    assert combo.currentData() == 2
    assert combo.currentText() == "Two"


def test_make_combo_no_initial_selects_first(qtbot):
    items = [(10, "Ten"), (20, "Twenty")]
    combo = make_combo(items)
    qtbot.addWidget(combo)
    assert combo.currentData() == 10


def test_make_combo_missing_initial_stays_at_first(qtbot):
    items = [(0, "A"), (1, "B")]
    combo = make_combo(items, initial=99)
    qtbot.addWidget(combo)
    # findData returns -1, so index doesn't change from 0
    assert combo.currentIndex() == 0


def test_add_field_with_hint_adds_two_rows(qtbot):
    form = QFormLayout()
    field = QWidget()
    add_field_with_hint(form, "Label", field, "This is a hint")
    # One row for the field, one row for the hint
    assert form.rowCount() == 2


def test_section_label_text_is_uppercased(qtbot):
    label = section_label("tracking")
    qtbot.addWidget(label)
    assert label.text() == "TRACKING"
    assert label.objectName() == "prefsSection"


def test_rotation_options_has_four_entries():
    assert len(ROTATION_OPTIONS) == 4
    assert ROTATION_OPTIONS[0] == (0, "None")
    assert ROTATION_OPTIONS[1][0] == 90


def test_calibres_by_key_matches_calibres():
    for key, _label, mm in CALIBRES:
        assert key in CALIBRES_BY_KEY
        assert CALIBRES_BY_KEY[key] == mm


def test_property_slider_initial_value(qtbot):
    slider = PropertySlider("brightness", 50.0, minimum=0.0, maximum=100.0, default=0.0)
    qtbot.addWidget(slider)
    assert abs(slider.value() - 50.0) < 1.0


def test_property_slider_set_value_no_signal(qtbot):
    slider = PropertySlider("contrast", 1.0, minimum=0.5, maximum=2.0, default=1.0, suffix="x")
    qtbot.addWidget(slider)
    received = []
    slider.value_changed.connect(lambda name, val: received.append((name, val)))
    slider.set_value(1.5)
    assert abs(slider.value() - 1.5) < 0.02
    assert received == []


def test_property_slider_emits_on_change(qtbot):
    slider = PropertySlider("brightness", 0.0, minimum=-100.0, maximum=100.0, default=0.0)
    qtbot.addWidget(slider)
    received = []
    slider.value_changed.connect(lambda name, val: received.append((name, val)))
    # Move to a clearly different position
    slider._slider.setValue(150)
    assert len(received) == 1
    assert received[0][0] == "brightness"
    assert received[0][1] > 0


def test_property_slider_reset_restores_default(qtbot):
    slider = PropertySlider("test", 75.0, minimum=0.0, maximum=100.0, default=50.0)
    qtbot.addWidget(slider)
    slider._reset.click()
    assert abs(slider.value() - 50.0) < 1.0
