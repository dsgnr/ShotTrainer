from __future__ import annotations

import pytest

from shottrainer.replay.player import TracePlayer
from shottrainer.tracking.models import TrackingSample


def _samples(n: int, dt: float = 0.01) -> list[TrackingSample]:
    """Build a small trace with ``n`` evenly spaced mapped samples."""
    return [
        TrackingSample(
            timestamp=i * dt,
            x_px=0.0,
            y_px=0.0,
            x_mm=float(i),
            y_mm=-float(i),
        )
        for i in range(n)
    ]


@pytest.fixture()
def player(qtbot):
    return TracePlayer()


def test_load_drops_unmapped_samples_and_emits_first_point(qtbot, player):
    mixed = [
        TrackingSample(timestamp=0.0, x_px=0.0, y_px=0.0, x_mm=1.0, y_mm=2.0),
        TrackingSample(timestamp=0.01, x_px=0.0, y_px=0.0, x_mm=None, y_mm=None),
        TrackingSample(timestamp=0.02, x_px=0.0, y_px=0.0, x_mm=3.0, y_mm=4.0),
    ]
    with qtbot.waitSignal(player.point, timeout=500) as blocker:
        player.load(mixed)
    # The unmapped sample is gone, so the trace has two entries and the
    # first emitted point is the first mapped sample.
    assert player.length == 2
    assert blocker.args == [1.0, 2.0]


def test_load_with_no_mapped_samples_is_a_safe_noop(player):
    unmapped = [
        TrackingSample(timestamp=0.0, x_px=0.0, y_px=0.0),
        TrackingSample(timestamp=0.01, x_px=0.0, y_px=0.0),
    ]
    player.load(unmapped)
    assert player.length == 0
    # Calling play and seek on an empty trace shouldn't blow up.
    player.play()
    player.seek_fraction(0.5)
    assert not player.is_playing


def test_seek_fraction_stays_in_range_and_does_not_auto_play(qtbot, player):
    player.load(_samples(11))
    with qtbot.waitSignal(player.progress, timeout=500) as blocker:
        player.seek_fraction(0.5)
    assert blocker.args == [pytest.approx(0.5)]
    assert not player.is_playing

    # Values outside 0..1 are pulled back to the nearest end.
    with qtbot.waitSignal(player.progress, timeout=500) as low:
        player.seek_fraction(-2.0)
    assert low.args == [0.0]
    with qtbot.waitSignal(player.progress, timeout=500) as high:
        player.seek_fraction(5.0)
    assert high.args == [1.0]


def test_set_speed_does_not_drop_below_the_minimum(player):
    player.set_speed(0.0)
    # The minimum is the only thing visible from the outside, so look
    # at the private speed directly to check it.
    assert player._speed == pytest.approx(0.1)
    player.set_speed(-3.0)
    assert player._speed == pytest.approx(0.1)
    player.set_speed(2.0)
    assert player._speed == pytest.approx(2.0)


def test_play_steps_through_every_sample_and_finishes(qtbot, player):
    seen: list[tuple[float, float]] = []
    player.point.connect(lambda x, y: seen.append((x, y)))
    player.load(_samples(6, dt=0.005))
    player.set_speed(50.0)  # drops each step to the 1 ms minimum

    with qtbot.waitSignal(player.finished, timeout=2000):
        player.play()

    # The loaded points come back in order, including the first one
    # that was emitted on load.
    expected = [(float(i), -float(i)) for i in range(6)]
    assert seen == expected
    assert not player.is_playing


def test_play_after_finishing_rewinds_to_the_start(qtbot, player):
    player.load(_samples(4, dt=0.005))
    player.set_speed(50.0)

    with qtbot.waitSignal(player.finished, timeout=2000):
        player.play()
    # Now the playhead is at the last sample. Pressing play again
    # should start the trace over.
    progress_values: list[float] = []
    points: list[tuple[float, float]] = []
    indices: list[int] = []
    player.progress.connect(progress_values.append)
    player.point.connect(lambda x, y: points.append((x, y)))
    player.index_changed.connect(indices.append)
    with qtbot.waitSignal(player.finished, timeout=2000):
        player.play()
        assert progress_values == [0.0]
        assert points == [(0.0, 0.0)]
        assert indices == [0]
    assert points == [(float(i), -float(i)) for i in range(4)]
    assert indices == [0, 1, 2, 3]
    assert progress_values[-1] == pytest.approx(1.0)


def test_pause_keeps_the_playhead_stop_rewinds_it(qtbot, player):
    player.load(_samples(20, dt=0.01))
    player.set_speed(2.0)

    # Run a few steps, then pause, and check the index hasn't moved back.
    player.play()
    qtbot.waitUntil(lambda: player._index > 2, timeout=2000)
    player.pause()
    paused_index = player._index
    assert not player.is_playing
    assert player._index == paused_index

    # Stop should return the playhead to the first sample.
    with qtbot.waitSignal(player.progress, timeout=500) as blocker:
        player.stop()
    assert blocker.args == [0.0]
    assert player._index == 0


def test_seeking_to_end_during_playback_finishes_without_advancing_past_trace(player):
    player.load(_samples(4, dt=10.0))
    finished = []
    points = []
    player.finished.connect(lambda: finished.append(True))
    player.point.connect(lambda x, y: points.append((x, y)))
    player.play()

    player.seek_fraction(1.0)

    assert not player.is_playing
    assert finished == [True]
    assert points == [(3.0, -3.0)]
    assert not player._timer.isActive()


def test_seeking_during_playback_uses_the_new_sample_timing(qtbot, player):
    samples = [
        TrackingSample(timestamp=ts, x_px=0.0, y_px=0.0, x_mm=float(i), y_mm=0.0)
        for i, ts in enumerate((0.0, 10.0, 10.01, 10.02))
    ]
    player.load(samples)
    player.play()

    with qtbot.waitSignal(player.finished, timeout=500):
        player.seek_fraction(2 / 3)

    assert not player.is_playing


def test_scrubbing_and_progress_follow_elapsed_time_for_irregular_samples(player):
    samples = [
        TrackingSample(timestamp=ts, x_px=0.0, y_px=0.0, x_mm=float(i), y_mm=0.0)
        for i, ts in enumerate((10.0, 10.1, 10.2, 11.0))
    ]
    progress = []
    player.progress.connect(progress.append)
    player.load(samples)
    player.play()
    player._step()
    player.pause()
    assert progress[-1] == pytest.approx(0.1)

    player.seek_fraction(0.5)
    assert player._index == 2
    assert progress[-1] == pytest.approx(0.2)
    player.seek_fraction(1.0)
    assert player._index == 3
    assert progress[-1] == 1.0


def test_replay_with_identical_timestamps_can_seek_without_division_by_zero(player):
    player.load(_samples(3, dt=0.0))
    progress = []
    player.progress.connect(progress.append)
    player.seek_fraction(1.0)
    assert player._index == 2
    assert progress[-1] == 1.0
