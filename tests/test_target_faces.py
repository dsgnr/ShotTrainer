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



def test_custom_face_loaded_from_data_dir(tmp_path, monkeypatch):
    from pathlib import Path

    import shottrainer.ui.target_faces as tf

    custom_file = tmp_path / "custom_target_faces.json"
    custom_file.write_text(
        '{"my_face": {"label": "My face", "rings": ['
        '{"radius_mm": 50.0, "label": "1"},'
        '{"radius_mm": 5.0, "label": "X"}'
        ']}}'
    )
    monkeypatch.setattr(tf, "custom_faces_path", lambda: Path(custom_file))

    keys = {k for k, _ in tf.list_target_faces()}
    assert "my_face" in keys
    assert tf.rings_for_face("my_face")[0].radius_mm == 50.0


def test_custom_face_with_garbage_file_is_ignored(tmp_path, monkeypatch):
    from pathlib import Path

    import shottrainer.ui.target_faces as tf

    custom_file = tmp_path / "custom_target_faces.json"
    custom_file.write_text("not json")
    monkeypatch.setattr(tf, "custom_faces_path", lambda: Path(custom_file))
    # Built-ins are still listed.
    keys = {k for k, _ in tf.list_target_faces()}
    assert "default" in keys
