"""A short rolling buffer of recent tracking samples.

It does two things. It keeps the last few seconds of trace in
memory so the shot coordinator can pick the sample nearest the
shot's timestamp and pull a pre/post window around it for
replay. It also holds samples for batched database writes so
the recorder doesn't open a transaction per frame.
"""

from __future__ import annotations

import bisect
from collections import deque
from collections.abc import Iterable

from shottrainer.tracking.models import TrackingSample


class TraceBuffer:
    def __init__(self, capacity: int = 6000) -> None:
        self._samples: deque[TrackingSample] = deque(maxlen=capacity)

    def __len__(self) -> int:
        return len(self._samples)

    @property
    def capacity(self) -> int | None:
        return self._samples.maxlen

    def append(self, sample: TrackingSample) -> None:
        self._samples.append(sample)

    def extend(self, samples: Iterable[TrackingSample]) -> None:
        self._samples.extend(samples)

    def clear(self) -> None:
        self._samples.clear()

    def snapshot(self) -> list[TrackingSample]:
        return list(self._samples)

    def nearest(self, timestamp: float) -> TrackingSample | None:
        if not self._samples:
            return None
        # Linear scan is fine: the buffer is small and time-ordered.
        ts = [s.timestamp for s in self._samples]
        i = bisect.bisect_left(ts, timestamp)
        candidates = []
        if i < len(ts):
            candidates.append(self._samples[i])
        if i > 0:
            candidates.append(self._samples[i - 1])
        if not candidates:
            return None
        return min(candidates, key=lambda s: abs(s.timestamp - timestamp))

    def window(self, start_ts: float, end_ts: float) -> list[TrackingSample]:
        return [s for s in self._samples if start_ts <= s.timestamp <= end_ts]
