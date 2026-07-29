//! Spots a sharp shot impulse in a stream of mono audio blocks.

use crate::models::{ShotDetectorSettings, ShotEvent};

/// Detects shots in consecutive blocks of mono samples.
///
/// The filter delay and the refractory timestamp persist between blocks.
/// Call [`ShotDetector::reset`] when a new session starts.
#[derive(Debug, Clone)]
pub struct ShotDetector {
    settings: ShotDetectorSettings,
    last_shot_ts: Option<f64>,
    filter_state: f32,
}

impl ShotDetector {
    pub fn new(settings: ShotDetectorSettings) -> Self {
        ShotDetector {
            settings,
            last_shot_ts: None,
            filter_state: 0.0,
        }
    }

    pub fn settings(&self) -> &ShotDetectorSettings {
        &self.settings
    }

    /// Clears the filter state and the refractory timestamp.
    pub fn reset(&mut self) {
        self.last_shot_ts = None;
        self.filter_state = 0.0;
    }

    /// Swaps in new settings and keeps the filter state and refractory timestamp.
    pub fn update_settings(&mut self, settings: ShotDetectorSettings) {
        self.settings = settings;
    }

    /// Processes one block of mono samples.
    ///
    /// An empty block returns `None` and leaves the filter state alone. A
    /// block with a NaN or infinite level never fires, and a NaN in the input
    /// stays in the filter state until [`ShotDetector::reset`], as with
    /// `scipy.signal.lfilter`.
    pub fn process_block(&mut self, samples: &[f32], block_start_ts: f64) -> Option<ShotEvent> {
        if samples.is_empty() {
            return None;
        }

        // One-pole DC blocker `y[n] = x[n] - x[n-1] + a * y[n-1]` in the
        // direct form II transposed order and `f32` precision that lfilter
        // uses. Separate multiply and add steps are needed to stay bit
        // identical, so no fused multiply-add.
        let alpha = self.settings.high_pass_alpha as f32;
        let mut z = self.filter_state;
        let mut sum_of_squares = 0.0_f64;
        let mut loudest = 0.0_f32;
        let mut loudest_index = 0;
        for (i, &x) in samples.iter().enumerate() {
            let y = x + z;
            z = -x + alpha * y;
            sum_of_squares += f64::from(y * y);
            let magnitude = y.abs();
            if magnitude > loudest {
                loudest = magnitude;
                loudest_index = i;
            }
        }
        self.filter_state = z;

        // numpy keeps the whole RMS calculation in `f32`. Accumulating the
        // squares in `f64` stays within 1e-6 of its dot product whatever the
        // summation order, and a sum beyond the `f32` range still becomes
        // infinity when rounded back.
        let mean_square = sum_of_squares as f32 / samples.len() as f32;
        let rms = f64::from(mean_square.sqrt());
        if !rms.is_finite() || rms < self.settings.threshold {
            return None;
        }

        if let Some(last) = self.last_shot_ts {
            let elapsed_ms = (block_start_ts - last) * 1000.0;
            if elapsed_ms < f64::from(self.settings.refractory_ms) {
                return None;
            }
        }

        // Python divides by the sample rate and raises when it is zero.
        if self.settings.sample_rate == 0 {
            return None;
        }
        let ts = block_start_ts + loudest_index as f64 / f64::from(self.settings.sample_rate);
        self.last_shot_ts = Some(ts);
        Some(ShotEvent {
            timestamp: ts,
            audio_level: rms,
            sample_rate: self.settings.sample_rate,
        })
    }
}

impl Default for ShotDetector {
    fn default() -> Self {
        ShotDetector::new(ShotDetectorSettings::default())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::ShotDetectorSettings;
    use crate::test_signals::{Segment, render, render_recipe};
    use proptest::prelude::*;
    use serde_json::Value;

    fn settings_from(value: &Value) -> ShotDetectorSettings {
        ShotDetectorSettings {
            threshold: value["threshold"].as_f64().unwrap(),
            refractory_ms: value["refractory_ms"].as_u64().unwrap() as u32,
            block_size: value["block_size"].as_u64().unwrap() as usize,
            sample_rate: value["sample_rate"].as_u64().unwrap() as u32,
            high_pass_alpha: value["high_pass_alpha"].as_f64().unwrap(),
        }
    }

    #[test]
    fn golden_cases_match_the_python_detector() {
        let golden = testkit::load_golden("shot_detector");
        let cases = golden["cases"].as_array().unwrap();
        assert!(cases.len() > 15, "only {} cases", cases.len());
        let mut checked = 0;
        for case in cases {
            let name = case["name"].as_str().unwrap();
            let mut detector = ShotDetector::new(settings_from(&case["settings"]));
            for (i, block) in case["blocks"].as_array().unwrap().iter().enumerate() {
                let context = format!("{name} block {i}");
                let pre = &block["pre"];
                if pre["reset"].as_bool() == Some(true) {
                    detector.reset();
                }
                if !pre["update"].is_null() {
                    detector.update_settings(settings_from(&pre["update"]));
                }
                let samples = render_recipe(&block["recipe"]);
                let ts = block["ts"].as_f64().unwrap();
                let actual = detector.process_block(&samples, ts);
                let expected = &block["expect"];
                match (actual, expected.as_array()) {
                    (None, None) => {}
                    (Some(event), Some(e)) => {
                        let (ets, elevel) = (e[0].as_f64().unwrap(), e[1].as_f64().unwrap());
                        assert!(
                            (event.timestamp - ets).abs() <= 1e-9,
                            "{context}: timestamp {} != {ets}",
                            event.timestamp
                        );
                        assert!(
                            (event.audio_level - elevel).abs() <= 1e-5 * elevel.abs(),
                            "{context}: level {} != {elevel}",
                            event.audio_level
                        );
                        assert_eq!(
                            event.sample_rate as u64,
                            e[2].as_u64().unwrap(),
                            "{context}"
                        );
                    }
                    (actual, expected) => {
                        panic!("{context}: got {actual:?}, expected {expected:?}")
                    }
                }
                checked += 1;
            }
        }
        let total: usize = cases
            .iter()
            .map(|c| c["blocks"].as_array().unwrap().len())
            .sum();
        assert_eq!(checked, total);
        assert!(checked > 40);
    }

    fn silence(n: usize) -> Vec<f32> {
        vec![0.0; n]
    }

    fn impulse(n: usize, position: usize, amplitude: f32) -> Vec<f32> {
        let mut block = silence(n);
        block[position] = amplitude;
        block
    }

    fn detector(threshold: f64, refractory_ms: u32) -> ShotDetector {
        ShotDetector::new(ShotDetectorSettings {
            threshold,
            refractory_ms,
            block_size: 512,
            sample_rate: 8000,
            high_pass_alpha: 0.97,
        })
    }

    #[test]
    fn silence_does_not_trigger() {
        let mut det = detector(0.05, 400);
        assert_eq!(det.process_block(&silence(512), 0.0), None);
    }

    #[test]
    fn loud_impulse_triggers() {
        let mut det = detector(0.02, 400);
        let event = det.process_block(&impulse(512, 128, 0.9), 10.0).unwrap();
        assert!((event.timestamp - (10.0 + 128.0 / 8000.0)).abs() < 1e-3);
        assert!(event.audio_level > 0.0);
        assert_eq!(event.sample_rate, 8000);
    }

    #[test]
    fn refractory_blocks_immediate_second_trigger() {
        let mut det = detector(0.02, 300);
        assert!(det.process_block(&impulse(512, 100, 0.9), 0.0).is_some());
        assert_eq!(det.process_block(&impulse(512, 100, 0.9), 0.05), None);
    }

    #[test]
    fn refractory_releases_after_window() {
        let mut det = detector(0.02, 200);
        det.process_block(&impulse(512, 100, 0.9), 0.0);
        assert!(det.process_block(&impulse(512, 100, 0.9), 0.5).is_some());
    }

    #[test]
    fn quiet_signal_below_threshold() {
        let mut det = detector(0.5, 400);
        let quiet = render(
            0,
            &[Segment::Noise {
                n: 512,
                amp: 0.015625,
            }],
        );
        assert_eq!(det.process_block(&quiet, 0.0), None);
    }

    #[test]
    fn reset_clears_refractory() {
        let mut det = detector(0.02, 500);
        det.process_block(&impulse(512, 100, 0.9), 0.0);
        det.reset();
        assert!(det.process_block(&impulse(512, 100, 0.9), 0.05).is_some());
    }

    #[test]
    fn empty_block_returns_none() {
        assert_eq!(detector(0.0001, 0).process_block(&[], 1.0), None);
    }

    #[test]
    fn nan_sample_gives_no_event_and_poisons_the_filter_state() {
        let mut det = detector(0.02, 0);
        let mut block = impulse(512, 100, 0.9);
        block[3] = f32::NAN;
        assert_eq!(det.process_block(&block, 0.0), None);
        // The state stays NaN, as it does with scipy's lfilter, until reset.
        assert_eq!(det.process_block(&impulse(512, 100, 0.9), 1.0), None);
        det.reset();
        assert!(det.process_block(&impulse(512, 100, 0.9), 2.0).is_some());
    }

    #[test]
    fn zero_sample_rate_gives_no_event() {
        let mut det = ShotDetector::new(ShotDetectorSettings {
            sample_rate: 0,
            threshold: 0.02,
            ..ShotDetectorSettings::default()
        });
        assert_eq!(det.process_block(&impulse(512, 100, 0.9), 0.0), None);
    }

    #[test]
    fn default_detector_uses_default_settings() {
        assert_eq!(
            ShotDetector::default().settings(),
            &ShotDetectorSettings::default()
        );
    }

    fn plan_block(loud: bool) -> Vec<f32> {
        if loud {
            impulse(512, 128, 0.9)
        } else {
            silence(512)
        }
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(200))]

        #[test]
        fn refractory_window_is_monotonic(
            plan in prop::collection::vec((any::<bool>(), 0.0f64..2.0), 1..40),
            refractory_ms in 50u32..800,
        ) {
            let mut det = detector(0.02, refractory_ms);
            let mut events = Vec::new();
            let mut block_ts = 0.0;
            for (loud, gap) in plan {
                block_ts += gap;
                if let Some(event) = det.process_block(&plan_block(loud), block_ts) {
                    events.push(event);
                }
            }
            let min_gap = f64::from(refractory_ms) / 1000.0;
            for pair in events.windows(2) {
                prop_assert!(pair[1].timestamp - pair[0].timestamp >= min_gap - 1e-9);
            }
        }

        #[test]
        fn reset_always_lets_the_next_loud_block_through(refractory_ms in 100u32..2000) {
            let mut det = detector(0.02, refractory_ms);
            prop_assert!(det.process_block(&impulse(512, 100, 0.9), 0.0).is_some());
            prop_assert!(det.process_block(&impulse(512, 100, 0.9), 0.001).is_none());
            det.reset();
            prop_assert!(det.process_block(&impulse(512, 100, 0.9), 0.001).is_some());
        }

        #[test]
        fn events_are_inside_their_block(
            blocks in prop::collection::vec(
                (prop::collection::vec(-1.0f32..=1.0, 1..700), 0.0f64..1000.0),
                1..8,
            ),
            threshold in 0.0001f64..0.5,
        ) {
            let mut det = detector(threshold, 0);
            for (samples, start) in blocks {
                if let Some(event) = det.process_block(&samples, start) {
                    prop_assert!(event.audio_level >= 0.0);
                    prop_assert!(event.timestamp >= start);
                    prop_assert!(event.timestamp <= start + samples.len() as f64 / 8000.0);
                }
            }
        }

        #[test]
        fn arbitrary_input_never_panics(
            blocks in prop::collection::vec(
                (
                    prop::collection::vec(any::<u32>().prop_map(f32::from_bits), 0..300),
                    any::<f64>(),
                ),
                1..6,
            ),
            threshold in any::<f64>(),
            alpha in any::<f64>(),
            sample_rate in any::<u32>(),
        ) {
            let mut det = ShotDetector::new(ShotDetectorSettings {
                threshold,
                refractory_ms: 0,
                block_size: 512,
                sample_rate,
                high_pass_alpha: alpha,
            });
            for (samples, start) in blocks {
                if let Some(event) = det.process_block(&samples, start) {
                    prop_assert!(event.audio_level.is_finite());
                }
            }
        }
    }
}
