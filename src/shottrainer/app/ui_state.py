"""Saves the window geometry and splitter layout between runs."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .paths import data_dir

log = logging.getLogger(__name__)


@dataclass(slots=True)
class UiState:
    window_geometry_b64: str = ""        # ``QByteArray.toBase64`` of ``saveGeometry``
    main_splitter_sizes: list[int] = field(default_factory=list)


def ui_state_path() -> Path:
    return data_dir() / "ui_state.json"


def load_ui_state(path: Path | None = None) -> UiState:
    p = path or ui_state_path()
    if not p.exists():
        return UiState()
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s. Using defaults", p, exc)
        return UiState()
    geometry = raw.get("window_geometry_b64", "")
    sizes = raw.get("main_splitter_sizes", [])
    if not isinstance(geometry, str) or not isinstance(sizes, list):
        return UiState()
    return UiState(
        window_geometry_b64=geometry,
        main_splitter_sizes=[int(s) for s in sizes if isinstance(s, int) or str(s).lstrip("-").isdigit()],
    )


def save_ui_state(state: UiState, path: Path | None = None) -> None:
    p = path or ui_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(state), indent=2))


def encode_geometry(geometry_bytes: bytes) -> str:
    return base64.b64encode(geometry_bytes).decode("ascii")


def decode_geometry(encoded: str) -> bytes:
    if not encoded:
        return b""
    try:
        return base64.b64decode(encoded.encode("ascii"))
    except ValueError:
        return b""
