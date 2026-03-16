"""Round-trip tests for the zero-offset store."""

from __future__ import annotations

from pathlib import Path

from shottrainer.app.zero_offset_store import load_zero_offset, save_zero_offset


def test_returns_zero_when_missing(tmp_path: Path):
    assert load_zero_offset(tmp_path / "missing.json") == (0.0, 0.0)


def test_round_trip_preserves_offset(tmp_path: Path):
    p = tmp_path / "zero.json"
    save_zero_offset((1.5, -2.5), p)
    assert load_zero_offset(p) == (1.5, -2.5)


def test_zero_offset_removes_file(tmp_path: Path):
    p = tmp_path / "zero.json"
    save_zero_offset((1.0, 2.0), p)
    assert p.exists()
    save_zero_offset((0.0, 0.0), p)
    assert not p.exists()


def test_none_removes_file(tmp_path: Path):
    p = tmp_path / "zero.json"
    save_zero_offset((1.0, 2.0), p)
    save_zero_offset(None, p)
    assert not p.exists()


def test_garbage_file_returns_zero(tmp_path: Path):
    p = tmp_path / "zero.json"
    p.write_text("not json")
    assert load_zero_offset(p) == (0.0, 0.0)
