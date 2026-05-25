"""Type checks shared by the JSON settings loaders."""

from __future__ import annotations

import math


def matches_setting_type(value: object, default: object) -> bool:
    """Accept finite numbers and exact JSON types without coercing strings or bools."""
    if isinstance(default, bool):
        return type(value) is bool
    if isinstance(default, int):
        return type(value) is int and -(2**31) <= value < 2**31
    if isinstance(default, float):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False
    return type(value) is type(default)
