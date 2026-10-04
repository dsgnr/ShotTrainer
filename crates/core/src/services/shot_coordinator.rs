//! Ties a detected shot back to the trace around it.

use super::trace_buffer::TraceBuffer;
use shottrainer_audio::models::ShotEvent;
use shottrainer_tracking::models::TrackingSample;

#[derive(Debug, Clone, PartialEq)]
pub struct ShotCoordinatorSettings {
    pub pre_shot_ms: i64,
    pub post_shot_ms: i64,
}

impl Default for ShotCoordinatorSettings {
    fn default() -> Self {
        ShotCoordinatorSettings {
            pre_shot_ms: 1500,
            post_shot_ms: 800,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct ShotResult {
    pub event: ShotEvent,
    pub sample: Option<TrackingSample>,
    pub trace: Vec<TrackingSample>,
}

#[derive(Debug, Clone, Default)]
pub struct ShotCoordinator {
    settings: ShotCoordinatorSettings,
}

impl ShotCoordinator {
    pub fn new(settings: ShotCoordinatorSettings) -> Self {
        ShotCoordinator { settings }
    }

    pub fn update_settings(&mut self, settings: ShotCoordinatorSettings) {
        self.settings = settings;
    }

    /// `sample` is `None` when the buffer is empty.
    pub fn handle_shot(&self, buffer: &TraceBuffer, event: ShotEvent) -> ShotResult {
        let nearest = buffer.nearest(event.timestamp);
        let start = event.timestamp - self.settings.pre_shot_ms as f64 / 1000.0;
        let end = event.timestamp + self.settings.post_shot_ms as f64 / 1000.0;
        let trace = buffer.window(start, end);
        if nearest.is_none() {
            log::info!(
                "Shot at {:.3} had no nearby tracking sample",
                event.timestamp
            );
        }
        ShotResult {
            event,
            sample: nearest.cloned(),
            trace,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::trace_fixture::*;
    use shottrainer_audio::models::ShotEvent;

    #[test]
    fn handle_shot_matches_python() {
        let mut checked = 0;
        let mut empty_buffer_shots = 0;
        for case in cases() {
            let mut buf = TraceBuffer::new(case["capacity"].as_u64().unwrap() as usize);
            buf.extend(samples(&case["appended"]));
            for shot in case["shots"].as_array().unwrap() {
                let coordinator = ShotCoordinator::new(ShotCoordinatorSettings {
                    pre_shot_ms: shot["pre_shot_ms"].as_i64().unwrap(),
                    post_shot_ms: shot["post_shot_ms"].as_i64().unwrap(),
                });
                let event = ShotEvent {
                    timestamp: number(&shot["timestamp"]),
                    audio_level: 0.5,
                    sample_rate: 48000,
                };
                let result = coordinator.handle_shot(&buf, event);
                let context = format!("{} {shot}", case["name"]);
                assert_eq!(result.event.timestamp.to_bits(), event.timestamp.to_bits());
                assert_ref(result.sample.as_ref(), &shot["sample"], &context);
                assert_refs(&result.trace, &shot["trace"], &context);
                if buf.is_empty() {
                    assert!(result.sample.is_none() && result.trace.is_empty());
                    empty_buffer_shots += 1;
                }
                checked += 1;
            }
        }
        assert!(checked > 500 && empty_buffer_shots > 0);
    }

    #[test]
    fn defaults_and_update_settings() {
        let defaults = ShotCoordinatorSettings::default();
        assert_eq!((defaults.pre_shot_ms, defaults.post_shot_ms), (1500, 800));
        let mut buf = TraceBuffer::default();
        buf.extend([0.0, 1.0, 2.0].map(|t| TrackingSample::new(t, 0.0, 0.0)));
        let mut c = ShotCoordinator::new(defaults);
        let event = ShotEvent {
            timestamp: 1.0,
            audio_level: 0.5,
            sample_rate: 48000,
        };
        assert_eq!(c.handle_shot(&buf, event).trace.len(), 2);
        c.update_settings(ShotCoordinatorSettings {
            pre_shot_ms: 0,
            post_shot_ms: 0,
        });
        assert_eq!(c.handle_shot(&buf, event).trace.len(), 1);
    }
}
