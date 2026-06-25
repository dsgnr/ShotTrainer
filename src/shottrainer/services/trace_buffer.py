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
    """A fixed-size queue of the most recent ``TrackingSample`` records.

    Older samples drop off silently once the queue fills up.
    Anything that old has either been written to the database
    already or isn't relevant to a shot in flight.
    """

    def __init__(self, capacity: int = 6000) -> None:
        self._samples: deque[TrackingSample] = deque(maxlen=capacity)

    def __len__(self) -> int:
        return len(self._samples)

    @property
    def capacity(self) -> int | None:
        """The deque's ``maxlen``, or ``None`` if the buffer is unbounded."""
        return self._samples.maxlen

    def append(self, sample: TrackingSample) -> None:
        """Add ``sample``, dropping the oldest one if the buffer is full."""
        self._samples.append(sample)

    def extend(self, samples: Iterable[TrackingSample]) -> None:
        """Add every sample in ``samples``, in order."""
        self._samples.extend(samples)

    def clear(self) -> None:
        """Drop every sample currently in the buffer."""
        self._samples.clear()

    def snapshot(self) -> list[TrackingSample]:
        """Return a list copy of the buffer for safe iteration."""
        return list(self._samples)

    def nearest(self, timestamp: float) -> TrackingSample | None:
        """Return the buffered sample whose timestamp is closest to ``timestamp``.

        ``None`` for an empty buffer. The shot coordinator uses
        this to tie an audio-detected shot to the trace sample
        captured nearest in time.
        """
        if not self._samples:
            return None
        # Snapshot to a list so ``bisect`` can index in O(1). Deque
        # indexing is O(n), and bisect's log(n) lookups would
        # multiply that out.
        samples = list(self._samples)
        i = bisect.bisect_left(samples, timestamp, key=lambda s: s.timestamp)
        candidates: list[TrackingSample] = []
        if i < len(samples):
            candidates.append(samples[i])
        if i > 0:
            candidates.append(samples[i - 1])
        if not candidates:
            return None
        return min(candidates, key=lambda s: abs(s.timestamp - timestamp))

    def window(self, start_ts: float, end_ts: float) -> list[TrackingSample]:
        """Return every buffered sample whose timestamp is in ``[start_ts, end_ts]``."""
        return [s for s in self._samples if start_ts <= s.timestamp <= end_ts]
