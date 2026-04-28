"""Holds the catalogue of selectable target faces.

Every face is JSON. The built-ins ship as data files under
``ui/assets/target_faces/`` and the user can drop their own into
``custom_target_faces.json`` in the application data directory.
The two sources are merged at lookup time and a custom face
shadows a built-in if they share the same key.

A face file looks like this (built-ins are one face per file,
the user file is a dict of faces):

```
{
  "label": "My face",
  "rings": [
    { "diameter_mm": 150.0, "label": "1" },
    { "diameter_mm": 10.0,  "label": "X" }
  ]
}
```

Each ring's ``diameter_mm`` is the full width of the printed circle.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .assets import asset_path
from .target_view import TargetRing

log = logging.getLogger(__name__)


_BUILT_IN_DIR = asset_path("target_faces")


def custom_faces_path() -> Path:
    # Late import to avoid circular: ``app.paths`` doesn't depend on UI.
    from shottrainer.app.paths import data_dir

    return data_dir() / "custom_target_faces.json"


def _parse_rings(rings_raw: list) -> list[TargetRing]:
    rings: list[TargetRing] = []
    for r in rings_raw:
        if not isinstance(r, dict):
            continue
        try:
            rings.append(TargetRing(float(r["diameter_mm"]), str(r.get("label") or "")))
        except (KeyError, TypeError, ValueError):
            continue
    return rings


def _parse_face(body: dict, fallback_key: str) -> tuple[str, tuple[TargetRing, ...]] | None:
    if not isinstance(body, dict):
        return None
    label = str(body.get("label") or fallback_key)
    rings_raw = body.get("rings", [])
    if not isinstance(rings_raw, list):
        return None
    rings = _parse_rings(rings_raw)
    if not rings:
        return None
    return (label, tuple(rings))


_built_in_cache: dict[str, tuple[str, tuple[TargetRing, ...]]] = {}


def _load_built_in_faces() -> dict[str, tuple[str, tuple[TargetRing, ...]]]:
    """Load every ``*.json`` face shipped under ``ui/assets/target_faces/``.

    The filename stem (so ``smallbore_50m.json`` becomes ``smallbore_50m``)
    is the stable key that ends up in
    :class:`Preferences.target_face`. The JSON's ``label`` is the
    human-readable string shown in the picker. Walking the
    directory means a new built-in face is a single drop-in, no
    code change. The result is cached for the lifetime of the
    process since the built-ins are data files that don't change.
    """
    if _built_in_cache:
        return _built_in_cache
    try:
        entries = sorted(_BUILT_IN_DIR.glob("*.json"))
    except OSError as exc:  # pragma: no cover - asset dir guaranteed to exist
        log.warning("Could not list built-in face directory: %s", exc)
        return _built_in_cache
    for path in entries:
        key = path.stem
        try:
            raw = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Could not read built-in face %s: %s", path, exc)
            continue
        parsed = _parse_face(raw, key)
        if parsed is not None:
            _built_in_cache[key] = parsed
    return _built_in_cache


_custom_cache: dict[str, tuple[str, tuple[TargetRing, ...]]] = {}
_custom_cache_mtime: float = -1.0


def reload_custom_faces() -> None:
    """Drop the cache so the next lookup re-reads the file."""
    global _custom_cache_mtime
    _custom_cache.clear()
    _custom_cache_mtime = -1.0


def _load_custom_faces() -> dict[str, tuple[str, tuple[TargetRing, ...]]]:
    global _custom_cache_mtime
    p = custom_faces_path()
    try:
        mtime = p.stat().st_mtime if p.exists() else -1.0
    except OSError:
        mtime = -1.0

    if mtime == _custom_cache_mtime:
        return _custom_cache

    _custom_cache.clear()
    _custom_cache_mtime = mtime
    if mtime < 0:
        return _custom_cache
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s", p, exc)
        return _custom_cache
    if not isinstance(raw, dict):
        return _custom_cache
    for key, body in raw.items():
        parsed = _parse_face(body, str(key))
        if parsed is not None:
            _custom_cache[str(key)] = parsed
    return _custom_cache


def _merged_faces() -> dict[str, tuple[str, tuple[TargetRing, ...]]]:
    """Built-ins plus custom faces. Custom entries shadow built-ins of the same key."""
    merged: dict[str, tuple[str, tuple[TargetRing, ...]]] = {}
    merged.update(_load_built_in_faces())
    merged.update(_load_custom_faces())
    return merged


def list_target_faces() -> list[tuple[str, str]]:
    """Return ``(key, label)`` pairs for every available face.

    ``default`` comes first so it's the obvious pick for new
    users. The rest are sorted by their human-readable label so
    disciplines cluster sensibly in the picker.
    """
    items = list(_merged_faces().items())

    def sort_key(item: tuple[str, tuple[str, tuple[TargetRing, ...]]]) -> tuple[int, str]:
        key, (label, _) = item
        return (0 if key == "default" else 1, label.lower())

    return [(key, label) for key, (label, _) in sorted(items, key=sort_key)]


def rings_for_face(name: str) -> tuple[TargetRing, ...]:
    """Return the rings for ``name``, falling back gracefully.

    The fallback walks through ``default`` (if present) and then
    the first face in the merged catalogue. Returns an empty
    tuple if nothing is loadable, so callers don't need a
    special branch for "no faces installed".
    """
    faces = _merged_faces()
    entry = faces.get(name)
    if entry is not None:
        return entry[1]
    if "default" in faces:
        return faces["default"][1]
    if faces:
        return next(iter(faces.values()))[1]
    return ()


def diagnostic_rings(rings: tuple[TargetRing, ...]) -> list[TargetRing]:
    """Pick a couple of rings worth reporting time-in-ring for.

    The smallest ring shows precision, a mid-sized one shows the
    hold area. Returns an empty list when no rings are available.
    """
    if not rings:
        return []
    sorted_rings = sorted(rings, key=lambda r: r.diameter_mm)
    if len(sorted_rings) == 1:
        return [sorted_rings[0]]
    return [sorted_rings[0], sorted_rings[len(sorted_rings) // 2]]
