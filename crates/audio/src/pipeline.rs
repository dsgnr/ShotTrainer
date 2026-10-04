//! Turns interleaved device buffers into timed levels and shot events.

use std::sync::Arc;

use crate::models::{ShotDetectorSettings, ShotEvent};
use crate::shot_detector::ShotDetector;

#[derive(Debug, Clone, PartialEq)]
pub enum AudioEvent {
    /// RMS of each block before the high-pass filter.
    Level(f64),
    Shot(ShotEvent),
    Started,
    Stopped,
    Error(String),
}

/// Seconds on the shared monotonic timeline.
pub type ClockFn = Arc<dyn Fn() -> f64 + Send + Sync>;

/// Cuts incoming audio into detector blocks and stamps each one.
pub struct AudioPipeline {
    settings: ShotDetectorSettings,
    detector: ShotDetector,
    pending: Vec<f32>,
    sample_rate: u32,
    channels: u16,
    clock: ClockFn,
}

impl AudioPipeline {
    /// `sample_rate` and `channels` describe the incoming interleaved buffers.
    /// The block size comes from `settings.block_size` and the detector always
    /// runs at `sample_rate`, whatever `settings.sample_rate` says.
    pub fn new(
        settings: ShotDetectorSettings,
        sample_rate: u32,
        channels: u16,
        clock: ClockFn,
    ) -> Self {
        let detector = ShotDetector::new(Self::detector_settings(&settings, sample_rate));
        AudioPipeline {
            settings,
            detector,
            pending: Vec::new(),
            sample_rate,
            channels,
            clock,
        }
    }

    fn detector_settings(
        settings: &ShotDetectorSettings,
        sample_rate: u32,
    ) -> ShotDetectorSettings {
        ShotDetectorSettings {
            sample_rate,
            ..settings.clone()
        }
    }

    /// A new block size applies from the next block that is cut.
    pub fn update_settings(&mut self, settings: ShotDetectorSettings) {
        self.detector
            .update_settings(Self::detector_settings(&settings, self.sample_rate));
        self.settings = settings;
    }

    /// Drops pending samples and clears the detector.
    pub fn reset(&mut self) {
        self.pending.clear();
        self.detector.reset();
    }

    /// Feeds one interleaved buffer that arrived now and returns the events
    /// for every block it completes, in order.
    ///
    /// The clock is read once per non-empty buffer, so the end of the buffer's
    /// last frame is at the arrival time. A trailing partial frame is dropped
    /// rather than carried, because a device delivers whole frames and keeping
    /// half of one would shift every later frame off its channel.
    pub fn push(&mut self, interleaved: &[f32]) -> Vec<AudioEvent> {
        let channels = usize::from(self.channels);
        if channels == 0 || self.sample_rate == 0 || interleaved.len() < channels {
            return Vec::new();
        }
        let arrival = (self.clock)();

        if channels == 1 {
            self.pending.extend_from_slice(interleaved);
        } else {
            let divisor = channels as f32;
            self.pending.extend(
                interleaved
                    .chunks_exact(channels)
                    .map(|frame| frame.iter().sum::<f32>() / divisor),
            );
        }

        // A zero block size would never drain, so it is treated as one frame.
        let block_size = self.settings.block_size.max(1);
        let total = self.pending.len();
        let rate = f64::from(self.sample_rate);
        let mut events = Vec::new();
        let mut start = 0;
        while total - start >= block_size {
            let end = start + block_size;
            let block = &self.pending[start..end];
            let frames_back = (total - start) as f64;
            let block_start_ts = arrival - frames_back / rate;

            events.push(AudioEvent::Level(rms(block)));
            if let Some(shot) = self.detector.process_block(block, block_start_ts) {
                events.push(AudioEvent::Shot(shot));
            }
            start = end;
        }
        self.pending.drain(..start);
        events
    }
}

fn rms(block: &[f32]) -> f64 {
    if block.is_empty() {
        return 0.0;
    }
    let sum_of_squares = block.iter().fold(0.0_f64, |acc, &x| acc + f64::from(x * x));
    f64::from((sum_of_squares as f32 / block.len() as f32).sqrt())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_signals::render_recipe;
    use std::sync::Mutex;

    fn fixed_clock(value: Arc<Mutex<f64>>) -> ClockFn {
        Arc::new(move || *value.lock().unwrap())
    }

    fn settings(block_size: usize, sample_rate: u32) -> ShotDetectorSettings {
        ShotDetectorSettings {
            threshold: 0.02,
            refractory_ms: 0,
            block_size,
            sample_rate,
            high_pass_alpha: 0.97,
        }
    }

    fn settings_from(value: &serde_json::Value) -> ShotDetectorSettings {
        ShotDetectorSettings {
            threshold: value["threshold"].as_f64().unwrap(),
            refractory_ms: value["refractory_ms"].as_u64().unwrap() as u32,
            block_size: value["block_size"].as_u64().unwrap() as usize,
            sample_rate: value["sample_rate"].as_u64().unwrap() as u32,
            high_pass_alpha: value["high_pass_alpha"].as_f64().unwrap(),
        }
    }

    #[test]
    fn golden_cases_match_the_python_listener() {
        let golden = testkit::load_golden("audio_pipeline");
        let cases = golden["cases"].as_array().unwrap();
        assert!(cases.len() >= 4);
        let mut shots = 0;
        for case in cases {
            let name = case["name"].as_str().unwrap();
            let cfg = settings_from(&case["settings"]);
            let now = Arc::new(Mutex::new(0.0));
            let mut pipeline =
                AudioPipeline::new(cfg.clone(), cfg.sample_rate, 1, fixed_clock(now.clone()));
            for (i, buffer) in case["buffers"].as_array().unwrap().iter().enumerate() {
                let context = format!("{name} buffer {i}");
                *now.lock().unwrap() = buffer["arrival"].as_f64().unwrap();
                let actual = pipeline.push(&render_recipe(&buffer["recipe"]));
                let expected = buffer["expect"].as_array().unwrap();
                assert_eq!(actual.len(), expected.len(), "{context}: {actual:?}");
                for (got, want) in actual.iter().zip(expected) {
                    let want = want.as_array().unwrap();
                    match (got, want[0].as_str().unwrap()) {
                        (AudioEvent::Level(level), "level") => {
                            let e = want[1].as_f64().unwrap();
                            assert!(
                                (level - e).abs() <= 1e-5 * e.abs(),
                                "{context}: level {level} != {e}"
                            );
                        }
                        (AudioEvent::Shot(shot), "shot") => {
                            let (ets, elevel) =
                                (want[1].as_f64().unwrap(), want[2].as_f64().unwrap());
                            assert!(
                                (shot.timestamp - ets).abs() <= 1e-9,
                                "{context}: timestamp {} != {ets}",
                                shot.timestamp
                            );
                            assert!(
                                (shot.audio_level - elevel).abs() <= 1e-5 * elevel.abs(),
                                "{context}: level {} != {elevel}",
                                shot.audio_level
                            );
                            assert_eq!(u64::from(shot.sample_rate), want[3].as_u64().unwrap());
                            shots += 1;
                        }
                        other => panic!("{context}: unexpected pair {other:?}"),
                    }
                }
            }
        }
        assert!(shots >= 4, "only {shots} shots checked");
    }

    /// Silence with a short loud burst every 3000 frames.
    fn test_signal(frames: usize) -> Vec<f32> {
        (0..frames)
            .map(|i| match i % 3000 {
                0..=9 => 0.75,
                _ => 0.0,
            })
            .collect()
    }

    fn run_in_chunks(signal: &[f32], chunk_sizes: &[usize], block: usize) -> Vec<AudioEvent> {
        let now = Arc::new(Mutex::new(0.0));
        let mut pipeline =
            AudioPipeline::new(settings(block, 8192), 8192, 1, fixed_clock(now.clone()));
        let mut events = Vec::new();
        let mut offset = 0;
        let mut sizes = chunk_sizes.iter().cycle();
        while offset < signal.len() {
            let size = (*sizes.next().unwrap()).min(signal.len() - offset);
            offset += size;
            *now.lock().unwrap() = offset as f64 / 8192.0;
            events.extend(pipeline.push(&signal[offset - size..offset]));
        }
        events
    }

    #[test]
    fn re_chunking_yields_the_same_events_and_timestamps() {
        let signal = test_signal(12288);
        let reference = run_in_chunks(&signal, &[256], 256);
        let shots = reference
            .iter()
            .filter(|e| matches!(e, AudioEvent::Shot(_)))
            .count();
        assert!(shots >= 3, "{shots} shots");
        assert_eq!(reference.len() - shots, 12288 / 256);
        for sizes in [
            vec![1],
            vec![7],
            vec![256],
            vec![1000],
            vec![1024],
            vec![3000],
            vec![1, 7, 256, 1000, 1024, 3000],
        ] {
            let events = run_in_chunks(&signal, &sizes, 256);
            assert_eq!(events.len(), reference.len(), "{sizes:?}");
            for (got, want) in events.iter().zip(&reference) {
                match (got, want) {
                    (AudioEvent::Level(a), AudioEvent::Level(b)) => {
                        assert!((a - b).abs() <= 1e-12, "{sizes:?}")
                    }
                    (AudioEvent::Shot(a), AudioEvent::Shot(b)) => {
                        assert!((a.timestamp - b.timestamp).abs() <= 1e-9, "{sizes:?}");
                        assert_eq!(a.audio_level, b.audio_level, "{sizes:?}");
                    }
                    _ => panic!("{sizes:?}: {got:?} vs {want:?}"),
                }
            }
        }
    }

    #[test]
    fn block_timestamps_follow_the_cumulative_frame_count() {
        let now = Arc::new(Mutex::new(0.0));
        let mut pipeline = AudioPipeline::new(settings(4, 8), 8, 1, fixed_clock(now.clone()));
        // Frames 0..3 are silent and frame 6 of the stream is a burst inside block 1.
        *now.lock().unwrap() = 10.0;
        let mut signal = vec![0.0_f32; 10];
        signal[6] = 0.5;
        let events = pipeline.push(&signal);
        // Ten frames end at t = 10, so frame k starts at 10 - (10 - k) / 8. Blocks
        // start at frames 0 and 4 and two frames stay pending.
        let shots: Vec<_> = events
            .iter()
            .filter_map(|e| match e {
                AudioEvent::Shot(s) => Some(*s),
                _ => None,
            })
            .collect();
        assert_eq!(shots.len(), 1);
        assert!((shots[0].timestamp - (10.0 - 6.0 / 8.0 + 2.0 / 8.0)).abs() <= 1e-12);
        // The two pending frames complete the next block four frames later.
        *now.lock().unwrap() = 10.5;
        let events = pipeline.push(&[0.0, 0.0]);
        assert_eq!(events, vec![AudioEvent::Level(0.0)]);
    }

    #[test]
    fn stereo_is_averaged_and_a_partial_frame_is_dropped() {
        let now = Arc::new(Mutex::new(1.0));
        let mut pipeline = AudioPipeline::new(settings(2, 8), 8, 2, fixed_clock(now));
        // Frames (0.5, -0.5) and (1.0, 0.0) average to 0.0 and 0.5, and the lone 0.9 is dropped.
        let events = pipeline.push(&[0.5, -0.5, 1.0, 0.0, 0.9]);
        let expected_rms = f64::from((0.25_f32 / 2.0).sqrt());
        assert_eq!(events.len(), 2, "{events:?}");
        assert_eq!(events[0], AudioEvent::Level(expected_rms));
        // The dropped half frame is not prepended to the next buffer.
        let events = pipeline.push(&[0.0, 0.0, 0.0, 0.0]);
        assert_eq!(events[0], AudioEvent::Level(0.0));
        assert_eq!(
            events
                .iter()
                .filter(|e| matches!(e, AudioEvent::Level(_)))
                .count(),
            1
        );
    }

    #[test]
    fn empty_buffers_return_nothing_and_skip_the_clock() {
        let calls = Arc::new(Mutex::new(0_u32));
        let counter = calls.clone();
        let clock: ClockFn = Arc::new(move || {
            *counter.lock().unwrap() += 1;
            0.0
        });
        let mut pipeline = AudioPipeline::new(settings(4, 8), 8, 2, clock);
        assert!(pipeline.push(&[]).is_empty());
        assert!(pipeline.push(&[0.5]).is_empty());
        assert_eq!(*calls.lock().unwrap(), 0);
        assert!(pipeline.push(&[0.0, 0.0]).is_empty());
        assert_eq!(*calls.lock().unwrap(), 1);
    }

    #[test]
    fn zero_channels_or_sample_rate_return_nothing() {
        let clock: ClockFn = Arc::new(|| 1.0);
        let mut no_channels = AudioPipeline::new(settings(4, 8), 8, 0, clock.clone());
        assert!(no_channels.push(&[0.0; 16]).is_empty());
        let mut no_rate = AudioPipeline::new(settings(4, 8), 0, 1, clock);
        assert!(no_rate.push(&[0.0; 16]).is_empty());
    }

    #[test]
    fn zero_block_size_does_not_hang() {
        let clock: ClockFn = Arc::new(|| 1.0);
        let mut pipeline = AudioPipeline::new(settings(0, 8), 8, 1, clock);
        assert_eq!(pipeline.push(&[0.0; 3]).len(), 3);
    }

    #[test]
    fn block_size_change_applies_at_the_next_boundary() {
        let clock: ClockFn = Arc::new(|| 1.0);
        let mut pipeline = AudioPipeline::new(settings(4, 8), 8, 1, clock);
        assert_eq!(pipeline.push(&[0.0; 6]).len(), 1);
        pipeline.update_settings(settings(2, 8));
        // Two pending frames now fill a block of the new size.
        assert_eq!(pipeline.push(&[0.0; 3]).len(), 2);
        assert_eq!(pipeline.push(&[0.0; 1]).len(), 1);
    }

    #[test]
    fn reset_clears_pending_samples_and_the_detector() {
        let clock: ClockFn = Arc::new(|| 1.0);
        let mut cfg = settings(4, 8);
        cfg.refractory_ms = 10_000;
        let mut pipeline = AudioPipeline::new(cfg, 8, 1, clock);
        assert!(pipeline.push(&[0.0; 3]).is_empty());
        pipeline.reset();
        let burst = [0.0, 0.5, 0.0, 0.0];
        let fired =
            |events: Vec<AudioEvent>| events.iter().any(|e| matches!(e, AudioEvent::Shot(_)));
        // With the three stale frames kept, the burst would straddle two blocks.
        assert!(fired(pipeline.push(&burst)));
        assert!(!fired(pipeline.push(&burst)));
        pipeline.reset();
        assert!(fired(pipeline.push(&burst)));
    }

    #[test]
    fn shot_events_carry_the_pipeline_sample_rate() {
        let clock: ClockFn = Arc::new(|| 5.0);
        let mut pipeline = AudioPipeline::new(settings(4, 44100), 8, 1, clock);
        let events = pipeline.push(&[0.0, 0.5, 0.0, 0.0]);
        let rate = events.iter().find_map(|e| match e {
            AudioEvent::Shot(s) => Some(s.sample_rate),
            _ => None,
        });
        assert_eq!(rate, Some(8));
        pipeline.update_settings(settings(4, 48000));
        pipeline.reset();
        let events = pipeline.push(&[0.0, 0.5, 0.0, 0.0]);
        assert!(
            events
                .iter()
                .any(|e| matches!(e, AudioEvent::Shot(s) if s.sample_rate == 8))
        );
    }

    #[test]
    fn a_ten_million_frame_buffer_is_processed() {
        let clock: ClockFn = Arc::new(|| 1000.0);
        let mut pipeline = AudioPipeline::new(settings(1024, 44100), 44100, 1, clock);
        let events = pipeline.push(&vec![0.0_f32; 10_000_000]);
        assert_eq!(events.len(), 10_000_000 / 1024);
    }
}
