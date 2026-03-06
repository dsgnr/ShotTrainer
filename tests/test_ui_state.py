from __future__ import annotations

from pathlib import Path

from shottrainer.app.ui_state import (
    UiState,
    decode_geometry,
    encode_geometry,
    load_ui_state,
    save_ui_state,
)


def test_returns_defaults_when_missing(tmp_path: Path):
    assert load_ui_state(tmp_path / "nope.json") == UiState()


def test_roundtrip(tmp_path: Path):
    p = tmp_path / "ui_state.json"
    state = UiState(window_geometry_b64="QmFzZTY0", main_splitter_sizes=[200, 400])
    save_ui_state(state, p)
    loaded = load_ui_state(p)
    assert loaded == state


def test_falls_back_on_garbage_file(tmp_path: Path):
    p = tmp_path / "ui_state.json"
    p.write_text("not json at all")
    assert load_ui_state(p) == UiState()


def test_geometry_encoding_roundtrip():
    payload = b"\x00\x01\x02hello"
    assert decode_geometry(encode_geometry(payload)) == payload


def test_decode_geometry_handles_empty():
    assert decode_geometry("") == b""


def test_decode_geometry_handles_garbage():
    assert decode_geometry("not base64 ###") == b""
