"""Helpers for slicing a trace around a shot timestamp."""

from __future__ import annotations

import bisect
from collections.abc import Sequence

from shottrainer.tracking.models import TrackingSample


def slice_window(
    samples: Sequence[TrackingSample],
    centre_ts: float,
    pre_ms: int,
    post_ms: int,
) -> list[TrackingSample]:
    if not samples:
        return []
    timestamps = [s.timestamp for s in samples]
    start = centre_ts - pre_ms / 1000.0
    end = centre_ts + post_ms / 1000.0
    lo = bisect.bisect_left(timestamps, start)
    hi = bisect.bisect_right(timestamps, end)
    return list(samples[lo:hi])


def index_of_nearest(samples: Sequence[TrackingSample], ts: float) -> int | None:
    if not samples:
        return None
    timestamps = [s.timestamp for s in samples]
    i = bisect.bisect_left(timestamps, ts)
    if i == 0:
        return 0
    if i >= len(samples):
        return len(samples) - 1
    before = samples[i - 1]
    after = samples[i]
    return i if abs(after.timestamp - ts) < abs(ts - before.timestamp) else i - 1
