from __future__ import annotations

from shottrainer.ui.target_faces import (
    diagnostic_rings,
    list_target_faces,
    rings_for_face,
)
from shottrainer.ui.target_view import TargetRing


def test_default_face_exists():
    keys = {k for k, _ in list_target_faces()}
    assert "default" in keys


def test_unknown_face_falls_back_to_default():
    rings = rings_for_face("nonsense")
    assert rings == rings_for_face("default")


def test_diagnostic_rings_picks_inner_and_mid():
    rings = (
        TargetRing(60.0, "outer"),
        TargetRing(30.0, "mid"),
        TargetRing(10.0, "inner"),
        TargetRing(2.0, "x"),
    )
    chosen = diagnostic_rings(rings)
    radii = [r.radius_mm for r in chosen]
    assert radii[0] == 2.0
    assert radii[1] in {10.0, 30.0}


def test_diagnostic_rings_handles_single_ring():
    rings = (TargetRing(5.0, "ten"),)
    assert diagnostic_rings(rings) == [rings[0]]


def test_diagnostic_rings_empty():
    assert diagnostic_rings(()) == []
