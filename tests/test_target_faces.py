from __future__ import annotations

from shottrainer.app.target_faces import (
    diagnostic_rings,
    face_for_name,
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


def test_face_for_name_returns_none_for_unknown():
    assert face_for_name("nonsense") is None


def test_built_in_face_carries_metadata():
    """The shipped 50m NSRA face has both calibre and overall-face
    metadata populated. The Preferences dialog uses these to
    auto-fill its diameter spinboxes."""
    face = face_for_name("nsra_50m_prone_rifle_mm12c_199618")
    assert face is not None
    assert face.shot_diameter_mm == 5.6
    # Black extends past the 4-ring (105.5 mm) to about 112.5 mm.
    assert face.face_diameter_mm == 112.5


def test_diagnostic_rings_picks_inner_and_mid():
    rings = (
        TargetRing(60.0, "outer"),
        TargetRing(30.0, "mid"),
        TargetRing(10.0, "inner"),
        TargetRing(2.0, "x"),
    )
    chosen = diagnostic_rings(rings)
    diameters = [r.diameter_mm for r in chosen]
    assert diameters[0] == 2.0
    assert diameters[1] in {10.0, 30.0}


def test_diagnostic_rings_handles_single_ring():
    rings = (TargetRing(5.0, "ten"),)
    assert diagnostic_rings(rings) == [rings[0]]


def test_diagnostic_rings_empty():
    assert diagnostic_rings(()) == []


def test_custom_face_loaded_from_data_dir(tmp_path, monkeypatch):
    from pathlib import Path

    import shottrainer.app.target_faces as tf

    custom_file = tmp_path / "custom_target_faces.json"
    custom_file.write_text(
        '{"my_face": {"label": "My face", "rings": ['
        '{"diameter_mm": 100.0, "label": "1"},'
        '{"diameter_mm": 10.0, "label": "X"}'
        "]}}"
    )
    monkeypatch.setattr(tf, "custom_faces_path", lambda: Path(custom_file))

    keys = {k for k, _ in tf.list_target_faces()}
    assert "my_face" in keys
    assert tf.rings_for_face("my_face")[0].diameter_mm == 100.0


def test_built_in_faces_are_discovered_dynamically(tmp_path, monkeypatch):
    """Dropping a face JSON into the built-in directory should make it
    appear in ``list_target_faces`` without any code change."""
    from pathlib import Path

    import shottrainer.app.target_faces as tf

    fake_dir = tmp_path / "faces"
    fake_dir.mkdir()
    (fake_dir / "made_up.json").write_text(
        '{"label": "Made Up Discipline", "rings": [{"diameter_mm": 50.0, "label": "1"}]}'
    )

    monkeypatch.setattr(tf, "_BUILT_IN_DIR", Path(fake_dir))
    # The built-in cache may already hold the real faces. Clear so the
    # patched directory is consulted, and clear again on teardown so
    # later tests rediscover the real assets dir.
    tf._built_in_cache.clear()
    monkeypatch.setattr(
        tf,
        "_built_in_cache",
        tf._built_in_cache,
    )

    try:
        keys = {k for k, _ in tf.list_target_faces()}
        assert "made_up" in keys
        assert tf.rings_for_face("made_up")[0].diameter_mm == 50.0
    finally:
        tf._built_in_cache.clear()


def test_face_metadata_is_parsed_from_json(tmp_path, monkeypatch):
    """A face JSON carrying ``shot_diameter_mm`` and
    ``face_diameter_mm`` exposes them on the resulting
    :class:`TargetFace`. Negative or non-numeric values are
    discarded so the dialog never auto-fills nonsense."""
    from pathlib import Path

    import shottrainer.app.target_faces as tf

    fake_dir = tmp_path / "faces"
    fake_dir.mkdir()
    (fake_dir / "with_meta.json").write_text(
        '{"label": "With meta", "shot_diameter_mm": 5.6,'
        ' "face_diameter_mm": 112.5,'
        ' "rings": [{"diameter_mm": 50.0, "label": "1"}]}'
    )
    (fake_dir / "bad_meta.json").write_text(
        '{"label": "Bad meta", "shot_diameter_mm": "huge",'
        ' "face_diameter_mm": -1,'
        ' "rings": [{"diameter_mm": 50.0, "label": "1"}]}'
    )

    monkeypatch.setattr(tf, "_BUILT_IN_DIR", Path(fake_dir))
    tf._built_in_cache.clear()

    try:
        good = tf.face_for_name("with_meta")
        assert good is not None
        assert good.shot_diameter_mm == 5.6
        assert good.face_diameter_mm == 112.5

        bad = tf.face_for_name("bad_meta")
        assert bad is not None
        assert bad.shot_diameter_mm is None
        assert bad.face_diameter_mm is None
    finally:
        tf._built_in_cache.clear()


def test_custom_face_with_garbage_file_is_ignored(tmp_path, monkeypatch):
    from pathlib import Path

    import shottrainer.app.target_faces as tf

    custom_file = tmp_path / "custom_target_faces.json"
    custom_file.write_text("not json")
    monkeypatch.setattr(tf, "custom_faces_path", lambda: Path(custom_file))
    # Built-ins are still listed.
    keys = {k for k, _ in tf.list_target_faces()}
    assert "default" in keys
