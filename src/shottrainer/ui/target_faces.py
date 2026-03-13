"""Holds the catalogue of selectable target faces.

Each face is just a list of scoring rings in millimetres. Real disciplines
have specific ring sets. The ones here are reasonable defaults. Users can
pick the one closest to what they're shooting on.
"""

from __future__ import annotations

from .target_view import TargetRing

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


def list_target_faces() -> list[tuple[str, str]]:
    return [(key, label) for key, (label, _) in _FACES.items()]


def rings_for_face(name: str) -> tuple[TargetRing, ...]:
    entry = _FACES.get(name) or _FACES["default"]
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
