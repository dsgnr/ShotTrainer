from __future__ import annotations

import json
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("raw", [None, [], "layout", 42, True])
def test_falls_back_on_non_object_json(tmp_path: Path, raw):
    p = tmp_path / "ui_state.json"
    p.write_text(json.dumps(raw))
    assert load_ui_state(p) == UiState()


def test_falls_back_on_invalid_encoding(tmp_path: Path):
    p = tmp_path / "ui_state.json"
    p.write_bytes(b"\xff\xfe")
    assert load_ui_state(p) == UiState()


def test_discards_invalid_splitter_sizes(tmp_path: Path):
    p = tmp_path / "ui_state.json"
    p.write_text(
        json.dumps(
            {
                "window_geometry_b64": "QmFzZTY0",
                "main_splitter_sizes": [200, "400", "--1", "²", -1, True, None, 2.5, 2**40, 0],
            }
        )
    )
    assert load_ui_state(p) == UiState(
        window_geometry_b64="QmFzZTY0", main_splitter_sizes=[200, 400, 0]
    )


def test_geometry_encoding_roundtrip():
    payload = b"\x00\x01\x02hello"
    assert decode_geometry(encode_geometry(payload)) == payload


def test_decode_geometry_handles_empty():
    assert decode_geometry("") == b""


def test_decode_geometry_handles_garbage():
    assert decode_geometry("not base64 ###") == b""
