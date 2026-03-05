"""Tests for the scoring service."""

from __future__ import annotations

import pytest

from shottrainer.services.scoring import (
    ScoringRing,
    label_to_value,
    score_shot,
    total_score,
)


def _air_rifle_rings() -> list[ScoringRing]:
    # Generic 1..10 layout ascending in radius. Values aren't from a real
    # discipline so the tests don't accidentally encode a federation
    # decision.
    return [
        ScoringRing(50.0, "1"),
        ScoringRing(40.0, "2"),
        ScoringRing(30.0, "3"),
        ScoringRing(20.0, "5"),
        ScoringRing(10.0, "8"),
        ScoringRing(5.0, "10"),
        ScoringRing(1.0, "X"),
    ]


def test_centre_shot_scores_innermost_ring():
    assert score_shot(0.0, 0.0, _air_rifle_rings()) == "X"


def test_shot_outside_rings_returns_empty():
    assert score_shot(60.0, 0.0, _air_rifle_rings()) == ""


def test_shot_diameter_extends_inwards():
    rings = _air_rifle_rings()
    # Centre 6 mm out, shot 4 mm wide. Centre alone sits in "10" (radius
    # 5 < 6 < 10) but a 4 mm wide shot edges into "10" because
    # distance - 2 = 4 <= 5. With diameter 0, it'd score "8".
    centre_only = score_shot(6.0, 0.0, rings)
    with_size = score_shot(6.0, 0.0, rings, shot_diameter_mm=4.0)
    assert centre_only == "8"
    assert with_size == "10"


def test_score_respects_centre_offset():
    rings = _air_rifle_rings()
    assert score_shot(10.0, 0.0, rings, centre=(10.0, 0.0)) == "X"


def test_unsorted_rings_still_score_correctly():
    shuffled = list(_air_rifle_rings())
    shuffled.reverse()
    assert score_shot(0.0, 0.0, shuffled) == "X"


def test_empty_rings_return_empty():
    assert score_shot(0.0, 0.0, []) == ""


def test_label_to_value_handles_x_and_numbers():
    assert label_to_value("X") == 10.0
    assert label_to_value("x") == 10.0
    assert label_to_value("10") == 10.0
    assert label_to_value("9.5") == 9.5
    assert label_to_value("inner") is None
    assert label_to_value("") is None


def test_total_score_skips_unparseable_labels():
    assert total_score(["10", "X", "miss", "9", ""]) == pytest.approx(29.0)
