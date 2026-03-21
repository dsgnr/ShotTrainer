"""Holds the catalogue of selectable target faces.

Each face is just a list of scoring rings in millimetres. Real disciplines
have specific ring sets. The ones here are reasonable defaults. Users can
pick the one closest to what they're shooting on, or add their own via a
JSON file in the application data directory.

Custom face file format (``custom_target_faces.json``):

```
{
  "my_face": {
    "label": "My custom face",
    "rings": [
      { "radius_mm": 75.0, "label": "1" },
      { "radius_mm": 5.0, "label": "X" }
    ]
  }
}
```

Built-ins are not overwritten by custom entries with the same key. The
custom entry simply takes precedence in the listing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .target_view import TargetRing

log = logging.getLogger(__name__)

_GENERIC = (
    TargetRing(75.0, "1"),
    TargetRing(60.0, "3"),
    TargetRing(45.0, "5"),
    TargetRing(30.0, "7"),
    TargetRing(15.0, "9"),
    TargetRing(5.0, "X"),
)


# 10 m air rifle (ISSF). Ring 1 is 45.5 mm radius, then 3.5 mm rings down to
# the inner ten of 0.25 mm radius. We round to one decimal place because the
# painter doesn't need sub-millimetre accuracy.
_AIR_RIFLE_10M = (
    TargetRing(22.75, "1"),
    TargetRing(19.25, "2"),
    TargetRing(15.75, "3"),
    TargetRing(12.25, "4"),
    TargetRing(8.75, "5"),
    TargetRing(5.25, "6"),
    TargetRing(1.75, "10"),
    TargetRing(0.25, "X"),
)


# 50 m smallbore (ISSF). Ring 1 is 81.25 mm radius, rings 8 mm apart down to
# the 10 ring of 5.2 mm and inner ten of 2.6 mm.
_SMALLBORE_50M = (
    TargetRing(81.25, "1"),
    TargetRing(73.25, "2"),
    TargetRing(65.25, "3"),
    TargetRing(57.25, "4"),
    TargetRing(49.25, "5"),
    TargetRing(41.25, "6"),
    TargetRing(33.25, "7"),
    TargetRing(25.25, "8"),
    TargetRing(17.25, "9"),
    TargetRing(9.25, "10"),
    TargetRing(2.6, "X"),
)


_FACES: dict[str, tuple[str, tuple[TargetRing, ...]]] = {
    "default": ("Default rings", _GENERIC),
    "air_rifle_10m": ("10 m air rifle", _AIR_RIFLE_10M),
    "smallbore_50m": ("50 m smallbore", _SMALLBORE_50M),
}


def custom_faces_path() -> Path:
    # Late import to avoid circular: ``app.paths`` doesn't depend on UI.
    from shottrainer.app.paths import data_dir

    return data_dir() / "custom_target_faces.json"


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
        if not isinstance(body, dict):
            continue
        label = str(body.get("label") or key)
        rings_raw = body.get("rings", [])
        if not isinstance(rings_raw, list):
            continue
        rings: list[TargetRing] = []
        for r in rings_raw:
            if not isinstance(r, dict):
                continue
            try:
                rings.append(TargetRing(float(r["radius_mm"]), str(r.get("label") or "")))
            except (KeyError, TypeError, ValueError):
                continue
        if rings:
            _custom_cache[str(key)] = (label, tuple(rings))
    return _custom_cache


def _merged_faces() -> dict[str, tuple[str, tuple[TargetRing, ...]]]:
    """Built-ins plus custom faces. Custom entries shadow built-ins of the same key."""
    merged: dict[str, tuple[str, tuple[TargetRing, ...]]] = {}
    merged.update(_FACES)
    merged.update(_load_custom_faces())
    return merged


def list_target_faces() -> list[tuple[str, str]]:
    return [(key, label) for key, (label, _) in _merged_faces().items()]


def rings_for_face(name: str) -> tuple[TargetRing, ...]:
    faces = _merged_faces()
    entry = faces.get(name) or faces["default"]
    return entry[1]


def diagnostic_rings(rings: tuple[TargetRing, ...]) -> list[TargetRing]:
    """Pick a couple of rings worth reporting time-in-ring for.

    The smallest ring shows precision, a mid-sized one shows the
    hold area. Returns an empty list when no rings are available.
    """
    if not rings:
        return []
    sorted_rings = sorted(rings, key=lambda r: r.radius_mm)
    if len(sorted_rings) == 1:
        return [sorted_rings[0]]
    return [sorted_rings[0], sorted_rings[len(sorted_rings) // 2]]
