//! Port of `replay/player.py`. Python drives the player with a single-shot
//! `QTimer`. Here the caller owns time: [`TracePlayer::deadline`] says when
//! the next step is due and [`TracePlayer::tick`] performs it, so the state
//! machine is tested without sleeping.

use shottrainer_core::replay::timeline::index_of_nearest;
use shottrainer_tracking::models::TrackingSample;

/// Python's `point`, `index_changed`, `progress` and `finished` signals.
#[derive(Debug, Clone, PartialEq)]
pub enum PlayerEvent {
    Point { x_mm: f64, y_mm: f64 },
    Index(usize),
    Progress(f64),
    Finished,
}

#[derive(Debug, Clone, PartialEq)]
pub struct TracePlayer {
    samples: Vec<TrackingSample>,
    index: usize,
    playing: bool,
    speed: f64,
    /// Seconds on the controller clock when the next step is due.
    deadline: Option<f64>,
}

impl Default for TracePlayer {
    fn default() -> Self {
        TracePlayer {
            samples: Vec::new(),
            index: 0,
            playing: false,
            speed: 1.0,
            deadline: None,
        }
    }
}

impl TracePlayer {
    pub fn new() -> Self {
        Self::default()
    }

    /// Replaces the trace, dropping samples without both millimetre
    /// coordinates. Like Python, the events of the implicit `stop` on the old
    /// trace come first, then the first point and a progress of zero.
    pub fn load(&mut self, samples: &[TrackingSample]) -> Vec<PlayerEvent> {
        let mut events = self.stop();
        self.samples = samples
            .iter()
            .filter(|s| s.x_mm.is_some() && s.y_mm.is_some())
            .cloned()
            .collect();
        self.index = 0;
        self.push_current(&mut events);
        events.push(PlayerEvent::Progress(0.0));
        events
    }

    /// Python `max(0.1, speed)`, which also maps NaN to the minimum.
    pub fn set_speed(&mut self, speed: f64) {
        self.speed = if speed > 0.1 { speed } else { 0.1 };
    }

    pub fn speed(&self) -> f64 {
        self.speed
    }

    /// Starts or resumes playback. At the last sample it rewinds first, so
    /// play replays a finished trace. Does nothing without samples or while
    /// already playing.
    pub fn play(&mut self, now: f64) -> Vec<PlayerEvent> {
        let mut events = Vec::new();
        if self.samples.is_empty() || self.playing {
            return events;
        }
        if self.index + 1 >= self.samples.len() {
            events.extend(self.stop());
        }
        self.playing = true;
        self.schedule_next(now, &mut events);
        events
    }

    /// Stops in place. The playhead stays where it is.
    pub fn pause(&mut self) {
        self.playing = false;
        self.deadline = None;
    }

    /// Pauses and rewinds to the first sample.
    pub fn stop(&mut self) -> Vec<PlayerEvent> {
        self.pause();
        self.index = 0;
        let mut events = Vec::new();
        self.push_current(&mut events);
        events.push(PlayerEvent::Progress(0.0));
        events
    }

    /// Moves the playhead to `fraction` of the recorded time, clamped to
    /// 0..=1 with NaN treated as 1 as Python's `min` and `max` do. Seeking
    /// keeps the play or pause state.
    pub fn seek_fraction(&mut self, fraction: f64, now: f64) -> Vec<PlayerEvent> {
        let mut events = Vec::new();
        let (Some(first), Some(last)) = (self.samples.first(), self.samples.last()) else {
            return events;
        };
        let fraction = if fraction < 1.0 { fraction } else { 1.0 };
        let fraction = if fraction > 0.0 { fraction } else { 0.0 };
        let duration = last.timestamp - first.timestamp;
        self.index = if duration > 0.0 {
            let timestamp = first.timestamp + fraction * duration;
            index_of_nearest(&self.samples, timestamp).unwrap_or(0)
        } else {
            // Python's `round` rounds halves to even.
            (fraction * (self.samples.len() - 1) as f64).round_ties_even() as usize
        };
        self.push_current(&mut events);
        events.push(self.progress());
        if self.playing {
            self.deadline = None;
            self.schedule_next(now, &mut events);
        }
        events
    }

    /// Advances one sample when the deadline has been reached. The next
    /// deadline is measured from `now`, as a restarted `QTimer` is.
    pub fn tick(&mut self, now: f64) -> Vec<PlayerEvent> {
        let mut events = Vec::new();
        if !self.playing || self.deadline.is_none_or(|due| now < due) {
            return events;
        }
        self.index += 1;
        self.push_current(&mut events);
        events.push(self.progress());
        self.schedule_next(now, &mut events);
        events
    }

    pub fn deadline(&self) -> Option<f64> {
        self.deadline
    }

    pub fn is_playing(&self) -> bool {
        self.playing
    }

    pub fn len(&self) -> usize {
        self.samples.len()
    }

    pub fn is_empty(&self) -> bool {
        self.samples.is_empty()
    }

    pub fn index(&self) -> usize {
        self.index
    }

    /// Sends `Finished` at the last sample. Otherwise the delay is the gap to
    /// the next sample divided by the speed, rounded half to even and at
    /// least 1 ms. A NaN gap also gives 1 ms.
    fn schedule_next(&mut self, now: f64, events: &mut Vec<PlayerEvent>) {
        if self.index + 1 >= self.samples.len() {
            self.playing = false;
            self.deadline = None;
            events.push(PlayerEvent::Finished);
            return;
        }
        let gap = self.samples[self.index + 1].timestamp - self.samples[self.index].timestamp;
        let delay_ms = (gap * 1000.0 / self.speed).round_ties_even();
        let delay_ms = if delay_ms > 1.0 { delay_ms } else { 1.0 };
        self.deadline = Some(now + delay_ms / 1000.0);
    }

    fn progress(&self) -> PlayerEvent {
        let first = self.samples[0].timestamp;
        let duration = self.samples[self.samples.len() - 1].timestamp - first;
        let fraction = if duration > 0.0 {
            (self.samples[self.index].timestamp - first) / duration
        } else {
            self.index as f64 / (self.samples.len() - 1).max(1) as f64
        };
        PlayerEvent::Progress(fraction)
    }

    fn push_current(&self, events: &mut Vec<PlayerEvent>) {
        let Some(sample) = self.samples.get(self.index) else {
            return;
        };
        if let (Some(x_mm), Some(y_mm)) = (sample.x_mm, sample.y_mm) {
            events.push(PlayerEvent::Point { x_mm, y_mm });
        }
        events.push(PlayerEvent::Index(self.index));
    }
}
#[cfg(test)]
mod tests {
    use super::*;

    fn mapped(timestamp: f64, x: f64, y: f64) -> TrackingSample {
        TrackingSample {
            x_mm: Some(x),
            y_mm: Some(y),
            ..TrackingSample::new(timestamp, 0.0, 0.0)
        }
    }

    /// `n` evenly spaced samples at `(i, -i)`.
    fn samples(n: usize, dt: f64) -> Vec<TrackingSample> {
        (0..n)
            .map(|i| mapped(i as f64 * dt, i as f64, -(i as f64)))
            .collect()
    }

    fn at(timestamps: &[f64]) -> Vec<TrackingSample> {
        timestamps
            .iter()
            .enumerate()
            .map(|(i, &ts)| mapped(ts, i as f64, 0.0))
            .collect()
    }

    fn points(events: &[PlayerEvent]) -> Vec<(f64, f64)> {
        events
            .iter()
            .filter_map(|e| match e {
                PlayerEvent::Point { x_mm, y_mm } => Some((*x_mm, *y_mm)),
                _ => None,
            })
            .collect()
    }

    fn last_progress(events: &[PlayerEvent]) -> f64 {
        events
            .iter()
            .rev()
            .find_map(|e| match e {
                PlayerEvent::Progress(p) => Some(*p),
                _ => None,
            })
            .expect("a progress event")
    }

    /// Ticks at each deadline until playback stops, returning every event.
    fn run_to_end(player: &mut TracePlayer) -> Vec<PlayerEvent> {
        let mut events = Vec::new();
        let mut guard = 0;
        while let Some(due) = player.deadline() {
            events.extend(player.tick(due));
            guard += 1;
            assert!(guard < 10_000, "playback did not finish");
        }
        events
    }

    #[test]
    fn load_drops_unmapped_samples_and_emits_first_point() {
        let mut player = TracePlayer::new();
        let mixed = [
            mapped(0.0, 1.0, 2.0),
            TrackingSample::new(0.01, 0.0, 0.0),
            mapped(0.02, 3.0, 4.0),
        ];
        let events = player.load(&mixed);
        assert_eq!(player.len(), 2);
        assert_eq!(
            events,
            [
                PlayerEvent::Progress(0.0),
                PlayerEvent::Point {
                    x_mm: 1.0,
                    y_mm: 2.0
                },
                PlayerEvent::Index(0),
                PlayerEvent::Progress(0.0),
            ]
        );
    }

    #[test]
    fn load_replays_the_stop_events_of_the_old_trace_first() {
        let mut player = TracePlayer::new();
        player.load(&samples(3, 0.01));
        player.seek_fraction(1.0, 0.0);
        let events = player.load(&[]);
        assert_eq!(
            events,
            [
                PlayerEvent::Point {
                    x_mm: 0.0,
                    y_mm: 0.0
                },
                PlayerEvent::Index(0),
                PlayerEvent::Progress(0.0),
                PlayerEvent::Progress(0.0),
            ]
        );
        assert!(player.is_empty());
    }

    #[test]
    fn load_with_no_mapped_samples_is_a_safe_noop() {
        let mut player = TracePlayer::new();
        player.load(&[
            TrackingSample::new(0.0, 0.0, 0.0),
            TrackingSample::new(0.01, 0.0, 0.0),
        ]);
        assert_eq!(player.len(), 0);
        assert!(player.play(0.0).is_empty());
        assert!(player.seek_fraction(0.5, 0.0).is_empty());
        assert!(player.tick(1.0).is_empty());
        assert!(!player.is_playing());
        assert_eq!(player.deadline(), None);
    }

    #[test]
    fn seek_fraction_stays_in_range_and_does_not_auto_play() {
        let mut player = TracePlayer::new();
        player.load(&samples(11, 0.01));
        let events = player.seek_fraction(0.5, 0.0);
        assert!((last_progress(&events) - 0.5).abs() < 1e-9);
        assert!(!player.is_playing());
        assert_eq!(last_progress(&player.seek_fraction(-2.0, 0.0)), 0.0);
        assert_eq!(last_progress(&player.seek_fraction(5.0, 0.0)), 1.0);
        assert_eq!(last_progress(&player.seek_fraction(f64::NAN, 0.0)), 1.0);
        assert_eq!(player.index(), 10);
    }

    #[test]
    fn set_speed_does_not_drop_below_the_minimum() {
        let mut player = TracePlayer::new();
        for (speed, expected) in [(0.0, 0.1), (-3.0, 0.1), (f64::NAN, 0.1), (2.0, 2.0)] {
            player.set_speed(speed);
            assert_eq!(player.speed(), expected, "speed {speed}");
        }
    }

    #[test]
    fn play_steps_through_every_sample_and_finishes() {
        let mut player = TracePlayer::new();
        let mut events = player.load(&samples(6, 0.005));
        player.set_speed(50.0);
        events.extend(player.play(0.0));
        // 5 ms at 50x rounds to 0 ms, which is raised to the 1 ms minimum.
        assert_eq!(player.deadline(), Some(0.001));
        events.extend(run_to_end(&mut player));
        let expected: Vec<(f64, f64)> = (0..6).map(|i| (i as f64, -(i as f64))).collect();
        assert_eq!(points(&events), expected);
        assert_eq!(events.last(), Some(&PlayerEvent::Finished));
        assert!(!player.is_playing());
    }

    #[test]
    fn play_after_finishing_rewinds_to_the_start() {
        let mut player = TracePlayer::new();
        player.load(&samples(4, 0.005));
        player.set_speed(50.0);
        player.play(0.0);
        run_to_end(&mut player);
        let start = player.play(1.0);
        assert_eq!(
            start,
            [
                PlayerEvent::Point {
                    x_mm: 0.0,
                    y_mm: 0.0
                },
                PlayerEvent::Index(0),
                PlayerEvent::Progress(0.0),
            ]
        );
        let rest = run_to_end(&mut player);
        let indices: Vec<usize> = start
            .iter()
            .chain(&rest)
            .filter_map(|e| match e {
                PlayerEvent::Index(i) => Some(*i),
                _ => None,
            })
            .collect();
        assert_eq!(indices, [0, 1, 2, 3]);
        assert!((last_progress(&rest) - 1.0).abs() < 1e-9);
    }

    #[test]
    fn pause_keeps_the_playhead_stop_rewinds_it() {
        let mut player = TracePlayer::new();
        player.load(&samples(20, 0.01));
        player.set_speed(2.0);
        player.play(0.0);
        for _ in 0..3 {
            let due = player.deadline().unwrap();
            player.tick(due);
        }
        player.pause();
        assert_eq!(player.index(), 3);
        assert!(!player.is_playing());
        assert_eq!(player.deadline(), None);
        assert!(player.tick(100.0).is_empty());
        assert_eq!(player.index(), 3);
        let events = player.stop();
        assert_eq!(last_progress(&events), 0.0);
        assert_eq!(player.index(), 0);
    }

    #[test]
    fn a_tick_before_the_deadline_does_nothing() {
        let mut player = TracePlayer::new();
        player.load(&samples(3, 0.5));
        player.play(10.0);
        assert_eq!(player.deadline(), Some(10.5));
        assert!(player.tick(10.499).is_empty());
        assert_eq!(player.index(), 0);
        assert!(!player.tick(10.5).is_empty());
        assert_eq!(player.index(), 1);
    }

    #[test]
    fn seeking_to_end_during_playback_finishes_without_advancing_past_trace() {
        let mut player = TracePlayer::new();
        player.load(&samples(4, 10.0));
        player.play(0.0);
        let events = player.seek_fraction(1.0, 0.0);
        assert!(!player.is_playing());
        assert_eq!(points(&events), [(3.0, -3.0)]);
        assert_eq!(events.last(), Some(&PlayerEvent::Finished));
        assert_eq!(player.deadline(), None);
    }

    #[test]
    fn seeking_during_playback_uses_the_new_sample_timing() {
        let mut player = TracePlayer::new();
        player.load(&at(&[0.0, 10.0, 10.01, 10.02]));
        player.play(0.0);
        assert_eq!(player.deadline(), Some(10.0));
        player.seek_fraction(2.0 / 3.0, 1.0);
        assert_eq!(player.index(), 1);
        let due = player.deadline().unwrap();
        assert!((due - 1.01).abs() < 1e-9, "{due}");
        let events = run_to_end(&mut player);
        assert_eq!(events.last(), Some(&PlayerEvent::Finished));
        assert!(!player.is_playing());
    }

    #[test]
    fn scrubbing_and_progress_follow_elapsed_time_for_irregular_samples() {
        let mut player = TracePlayer::new();
        player.load(&at(&[10.0, 10.1, 10.2, 11.0]));
        player.play(0.0);
        let due = player.deadline().unwrap();
        let events = player.tick(due);
        player.pause();
        assert!((last_progress(&events) - 0.1).abs() < 1e-9);
        let events = player.seek_fraction(0.5, 0.0);
        assert_eq!(player.index(), 2);
        assert!((last_progress(&events) - 0.2).abs() < 1e-9);
        let events = player.seek_fraction(1.0, 0.0);
        assert_eq!(player.index(), 3);
        assert_eq!(last_progress(&events), 1.0);
    }

    #[test]
    fn replay_with_identical_timestamps_can_seek_without_division_by_zero() {
        let mut player = TracePlayer::new();
        player.load(&samples(3, 0.0));
        let events = player.seek_fraction(1.0, 0.0);
        assert_eq!(player.index(), 2);
        assert_eq!(last_progress(&events), 1.0);
    }

    #[test]
    fn halves_round_to_even_as_in_python() {
        let mut player = TracePlayer::new();
        player.load(&samples(6, 0.0));
        player.seek_fraction(0.5, 0.0);
        assert_eq!(player.index(), 2, "2.5 rounds to 2");
        let mut player = TracePlayer::new();
        player.load(&at(&[0.0, 0.0025, 1.0]));
        player.play(0.0);
        assert_eq!(player.deadline(), Some(0.002), "2.5 ms rounds to 2 ms");
    }

    #[test]
    fn a_nan_gap_waits_the_minimum() {
        let mut player = TracePlayer::new();
        player.load(&at(&[0.0, f64::NAN, 1.0]));
        player.play(0.0);
        assert_eq!(player.deadline(), Some(0.001));
    }
}
