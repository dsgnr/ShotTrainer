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
  "shot_diameter_mm": 5.6,
  "face_diameter_mm": 112.5,
  "rings": [
    { "diameter_mm": 150.0, "label": "1" },
    { "diameter_mm": 10.0,  "label": "X" }
  ]
}
```

``rings[i].diameter_mm`` is the full width of each printed
scoring circle. ``shot_diameter_mm`` is the calibre the face
was designed for. ``face_diameter_mm`` is the diameter of the
black aiming area on the printed target (often equal to or a
few mm larger than the outermost scoring ring). The live
tracker uses it as the "tracking circle" size by default. The
last two fields are optional. A face without them is still
valid and the Preferences dialog will leave the user's
spinbox values alone.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .paths import data_dir

log = logging.getLogger(__name__)


# Built-in face JSON files ship under ``ui/assets/target_faces/``
# so the packaging step bundles them alongside icons and other
# UI resources. The catalogue is domain config, so we reach the
# directory via a path constant rather than importing the UI
# assets helper.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_BUILT_IN_DIR = _PACKAGE_ROOT / "ui" / "assets" / "target_faces"


@dataclass(frozen=True, slots=True)
class TargetRing:
    """A single scoring ring on a target face.

    Domain type, no Qt imports. Re-exported from the UI's target
    view for backward compatibility with widgets that already
    import it from there.
    """

    diameter_mm: float
    label: str | None = None


@dataclass(frozen=True, slots=True)
class TargetFace:
    """A target face and the metadata the rest of the app cares about."""

    key: str
    label: str
    rings: tuple[TargetRing, ...]
    shot_diameter_mm: float | None = None
    face_diameter_mm: float | None = None


def custom_faces_path() -> Path:
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


def _optional_positive_float(body: dict, field: str) -> float | None:
    """Coerce ``body[field]`` to a positive float, or ``None`` if it can't."""
    raw = body.get(field)
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _parse_face(body: dict, key: str) -> TargetFace | None:
    if not isinstance(body, dict):
        return None
    rings_raw = body.get("rings", [])
    if not isinstance(rings_raw, list):
        return None
    rings = _parse_rings(rings_raw)
    if not rings:
        return None
    return TargetFace(
        key=key,
        label=str(body.get("label") or key),
        rings=tuple(rings),
        shot_diameter_mm=_optional_positive_float(body, "shot_diameter_mm"),
        face_diameter_mm=_optional_positive_float(body, "face_diameter_mm"),
    )


_built_in_cache: dict[str, TargetFace] = {}


def _load_built_in_faces() -> dict[str, TargetFace]:
    """Load every ``*.json`` face shipped under ``ui/assets/target_faces/``.

    The filename stem (so ``smallbore_50m.json`` → ``smallbore_50m``)
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
        face = _parse_face(raw, key)
        if face is not None:
            _built_in_cache[key] = face
    return _built_in_cache


_custom_cache: dict[str, TargetFace] = {}
_custom_cache_mtime: float = -1.0


def reload_custom_faces() -> None:
    """Drop the cache so the next lookup re-reads the file."""
    global _custom_cache_mtime
    _custom_cache.clear()
    _custom_cache_mtime = -1.0


def _load_custom_faces() -> dict[str, TargetFace]:
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
        face = _parse_face(body, str(key))
        if face is not None:
            _custom_cache[str(key)] = face
    return _custom_cache


def _merged_faces() -> dict[str, TargetFace]:
    """Built-ins plus custom faces. Custom entries shadow built-ins of the same key."""
    merged: dict[str, TargetFace] = {}
    merged.update(_load_built_in_faces())
    merged.update(_load_custom_faces())
    return merged


def list_target_faces() -> list[tuple[str, str]]:
    """Return ``(key, label)`` pairs for every available face.

    ``default`` comes first so it's the obvious pick for new
    users. The rest are sorted by their human-readable label so
    disciplines cluster sensibly in the picker.
    """
    items = list(_merged_faces().values())

    def sort_key(face: TargetFace) -> tuple[int, str]:
        return (0 if face.key == "default" else 1, face.label.lower())

    return [(face.key, face.label) for face in sorted(items, key=sort_key)]


def face_for_name(name: str) -> TargetFace | None:
    """Return the full :class:`TargetFace` for ``name``, or ``None``.

    Unlike :func:`rings_for_face`, this does *not* fall back to
    another face when ``name`` is unknown. Callers that want a
    fallback should handle it themselves so the UI doesn't end up
    silently auto-populating from an unrelated face.
    """
    return _merged_faces().get(name)


def rings_for_face(name: str) -> tuple[TargetRing, ...]:
    """Return the rings for ``name``, falling back gracefully.

    The fallback walks through ``default`` (if present) and then
    the first face in the merged catalogue. Returns an empty
    tuple if nothing is loadable, so callers don't need a
    special branch for "no faces installed".
    """
    faces = _merged_faces()
    face = faces.get(name)
    if face is not None:
        return face.rings
    if "default" in faces:
        return faces["default"].rings
    if faces:
        return next(iter(faces.values())).rings
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
