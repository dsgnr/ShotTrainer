"""Save and reload the user's selected camera, by name.

Camera *indices* aren't stable. They change when USB devices
attach in a different order or when a different machine has a
different number of cameras built in. So we save the camera's
displayed name and match on that next time the app opens, with
the saved index and then index 0 as fallbacks.

Stored as a small JSON file next to the other state files so the
preferences dialog stays focused on user-tunable settings.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import data_dir

log = logging.getLogger(__name__)


@dataclass(slots=True)
class CameraSelection:
    name: str = ""
    # ``None`` means "no camera selected". Persisted as ``null``
    # in the JSON file. The loader treats a missing field as
    # ``0`` for backward compatibility with older files.
    index: int | None = 0


def camera_selection_path() -> Path:
    return data_dir() / "camera_selection.json"


def load_camera_selection(path: Path | None = None) -> CameraSelection:
    p = path or camera_selection_path()
    if not p.exists():
        return CameraSelection()
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s", p, exc)
        return CameraSelection()
    raw_index = raw.get("index")
    return CameraSelection(
        name=str(raw.get("name", "")),
        index=int(raw_index) if isinstance(raw_index, int) else None,
    )


def save_camera_selection(
    selection: CameraSelection, path: Path | None = None
) -> None:
    p = path or camera_selection_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(selection), indent=2))


def resolve_camera_index(
    selection: CameraSelection,
    available: Sequence[tuple[int, str]],
) -> int:
    """Pick the best device index given a saved selection.

    Tries each option in order. First, a device with a
    matching name. Failing that, the saved index when it is
    still in the list. Failing that, the first available
    index, which is usually 0.

    Falls back to ``0`` when ``available`` is empty and the saved
    selection has no usable index. Callers that want to respect a
    "no camera" choice should check ``selection.index is None``
    themselves first.
    """
    if not available:
        return selection.index if selection.index is not None else 0
    if selection.name:
        for idx, name in available:
            if name == selection.name:
                return idx
    indices = {idx for idx, _ in available}
    if selection.index is not None and selection.index in indices:
        return selection.index
    return available[0][0]
