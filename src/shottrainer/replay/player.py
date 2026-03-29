"""Plays a saved trace back at the original speed (or scrubbed)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QObject, QTimer, Signal

from shottrainer.tracking.models import TrackingSample


class TracePlayer(QObject):
    """Plays a trace back at its original sample timing, or by scrubbing.

    Uses a single-shot ``QTimer`` whose interval is the gap
    between the current sample and the next, so playback
    respects the original cadence even when frames weren't
    evenly spaced. ``speed`` is a multiplier, where ``2.0``
    plays back at half the gap and ``0.5`` at double.
    """

    point = Signal(float, float)  # x_mm, y_mm
    index_changed = Signal(int)
    progress = Signal(float)       # 0.0..1.0
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._samples: list[TrackingSample] = []
        self._index: int = 0
        self._playing: bool = False
        self._speed: float = 1.0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._step)

    def load(self, samples: Sequence[TrackingSample]) -> None:
        """Replace the loaded trace, dropping samples without mm coordinates.

        Resets the playhead to the first sample and sends out an
        initial ``index_changed`` so the view can position itself
        before the user presses play.
        """
        self.stop()
        self._samples = [s for s in samples if s.x_mm is not None and s.y_mm is not None]
        self._index = 0
        self._emit_current()
        self.progress.emit(0.0)

    def set_speed(self, speed: float) -> None:
        """Scale the playback rate. Held to a minimum of 0.1x."""
        self._speed = max(0.1, speed)

    def play(self) -> None:
        """Start (or resume) playback from the current playhead.

        Does nothing when no trace is loaded, or when playback
        is already running. Reaching the end and pressing play
        again rewinds to the start, so the play button can
        replay without an explicit reset.
        """
        if not self._samples or self._playing:
            return
        if self._index >= len(self._samples) - 1:
            self._index = 0
        self._playing = True
        self._schedule_next()

    def pause(self) -> None:
        """Stop the timer in place. The playhead stays where it is."""
        self._playing = False
        self._timer.stop()

    def stop(self) -> None:
        """Pause and rewind to the start of the trace."""
        self.pause()
        self._index = 0
        if self._samples:
            self._emit_current()
        self.progress.emit(0.0)

    def seek_fraction(self, f: float) -> None:
        """Jump the playhead to ``f`` (0.0..1.0) along the trace.

        Out-of-range values are kept inside 0..1. Seeking doesn't
        auto-resume playback, so the user can scrub without
        losing their pause state.
        """
        if not self._samples:
            return
        f = max(0.0, min(1.0, f))
        self._index = round(f * (len(self._samples) - 1))
        self._emit_current()
        self.progress.emit(self._index / max(1, len(self._samples) - 1))

    @property
    def is_playing(self) -> bool:
        """``True`` while the timer is actively advancing the playhead."""
        return self._playing

    @property
    def length(self) -> int:
        """Number of samples in the loaded trace."""
        return len(self._samples)

    def _schedule_next(self) -> None:
        """Set the timer to go off when the next sample's timestamp would arrive.

        Sends out ``finished`` and stops playing once the playhead
        reaches the last sample.
        """
        if self._index >= len(self._samples) - 1:
            self._playing = False
            self.finished.emit()
            return
        cur = self._samples[self._index]
        nxt = self._samples[self._index + 1]
        delay_ms = max(1, round((nxt.timestamp - cur.timestamp) * 1000.0 / self._speed))
        self._timer.start(delay_ms)

    def _step(self) -> None:
        """Advance one sample. Called by the timer's ``timeout`` signal."""
        if not self._playing:
            return
        self._index += 1
        self._emit_current()
        self.progress.emit(self._index / max(1, len(self._samples) - 1))
        self._schedule_next()

    def _emit_current(self) -> None:
        """Notify listeners about the sample at ``self._index``."""
        if not self._samples:
            return
        s = self._samples[self._index]
        if s.x_mm is not None and s.y_mm is not None:
            self.point.emit(float(s.x_mm), float(s.y_mm))
        self.index_changed.emit(self._index)
