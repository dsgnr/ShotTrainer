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
    """Return the contiguous samples within ``[centre - pre, centre + post]``.

    ``samples`` is assumed sorted by timestamp (the repository
    queries are ``ORDER BY ts``). The helper uses ``bisect`` with
    a ``key`` rather than building a parallel list of timestamps,
    so the cost is logarithmic and there's no allocation on the
    common path.
    """
    if not samples:
        return []
    start = centre_ts - pre_ms / 1000.0
    end = centre_ts + post_ms / 1000.0
    lo = bisect.bisect_left(samples, start, key=lambda s: s.timestamp)
    hi = bisect.bisect_right(samples, end, key=lambda s: s.timestamp)
    return list(samples[lo:hi])


def index_of_nearest(samples: Sequence[TrackingSample], ts: float) -> int | None:
    """Return the index of the sample closest to ``ts``, or ``None`` if empty.

    ``samples`` must be sorted by timestamp. As with
    :func:`slice_window`, uses ``bisect`` with a ``key`` to avoid
    building a parallel list.
    """
    if not samples:
        return None
    i = bisect.bisect_left(samples, ts, key=lambda s: s.timestamp)
    if i == 0:
        return 0
    if i >= len(samples):
        return len(samples) - 1
    before = samples[i - 1]
    after = samples[i]
    return i if abs(after.timestamp - ts) < abs(ts - before.timestamp) else i - 1
