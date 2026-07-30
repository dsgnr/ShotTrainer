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
        ScoringRing(1.0, "X"),
        ScoringRing(5.0, "10"),
        ScoringRing(10.0, "8"),
        ScoringRing(20.0, "5"),
        ScoringRing(30.0, "3"),
        ScoringRing(40.0, "2"),
        ScoringRing(50.0, "1"),
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


def test_unsorted_rings_score_against_first_match_in_order():
    """``score_shot`` no longer sorts defensively. The contract is
    that the caller pre-sorts. With reversed rings (largest first) a
    centred shot still scores the first ring it hits, which happens
    to be the outermost. This documents the new contract so a future
    accidental shuffle of the boundary builder gets noticed."""
    descending = list(reversed(_air_rifle_rings()))
    assert score_shot(0.0, 0.0, descending) == "1"


def test_empty_rings_return_empty():
    assert score_shot(0.0, 0.0, []) == ""


def test_outward_scoring_awards_smallest_ring_shot_is_inside():
    """For outward-scored targets, the ring labels assign higher
    values to larger rings. The scoring algorithm still picks the
    smallest ring the shot fits inside. The label scheme makes
    centre shots low and edge shots high.

    With outward scoring, a shot touching a ring boundary scores
    the ring it's leaving (the larger one) rather than the one
    it's entering (the smaller one). This is the opposite of
    inward scoring where touching a boundary scores the inner ring.
    """
    rings = [
        ScoringRing(10.0, "1"),   # centre, low value
        ScoringRing(25.0, "5"),
        ScoringRing(50.0, "10"),  # edge, high value
    ]
    # Shot at 40mm from centre is outside 25mm ring, inside 50mm.
    # With outward scoring, the ring boundary the shot is between
    # (25-50) scores the outer ring's label.
    assert score_shot(40.0, 0.0, rings, scoring_direction="outward") == "10"
    # Shot at 20mm is between 10mm and 25mm boundaries.
    # With outward scoring, the outer ring (25mm) gives "5".
    assert score_shot(20.0, 0.0, rings, scoring_direction="outward") == "5"
    # Shot dead centre is inside 10mm ring. Scores "1".
    assert score_shot(0.0, 0.0, rings, scoring_direction="outward") == "1"
    # Shot outside all rings is a miss.
    assert score_shot(60.0, 0.0, rings, scoring_direction="outward") == ""


def test_outward_scoring_with_shot_diameter():
    """Shot edge touching the ring counts for the outer ring."""
    rings = [
        ScoringRing(10.0, "1"),
        ScoringRing(30.0, "5"),
    ]
    # Shot centre at 12mm with 4mm diameter has its edge at 10mm,
    # which touches the 10mm ring boundary. With outward scoring,
    # the shot is between 10mm and 30mm, so it scores "5".
    # But edge at 10mm means it touches the 10mm boundary...
    # With outward scoring, touching the inner boundary means
    # you're still in the outer zone.
    assert score_shot(12.0, 0.0, rings, shot_diameter_mm=4.0, scoring_direction="outward") == "5"


def test_label_to_value_handles_x_and_numbers():
    assert label_to_value("X") == 10.0
    assert label_to_value("x") == 10.0
    assert label_to_value("10") == 10.0
    assert label_to_value("9.5") == 9.5
    assert label_to_value("inner") is None
    assert label_to_value("") is None


def test_total_score_skips_unparseable_labels():
    assert total_score(["10", "X", "miss", "9", ""]) == pytest.approx(29.0)
