//! Test doubles for the hardware and OpenCV boundaries.

use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

use shottrainer_tracking::detector::{DetectorSettings, TargetDetector};
use shottrainer_tracking::frame::Frame;
use shottrainer_tracking::models::Detection;

/// Returns queued detections in order, then not-found, and keeps every
/// frame it is given.
#[derive(Default)]
pub struct ScriptedDetector {
    pub queue: Arc<Mutex<VecDeque<Detection>>>,
    pub seen: Arc<Mutex<Vec<Frame>>>,
    pub settings: DetectorSettings,
}

impl ScriptedDetector {
    pub fn push(&self, detection: Detection) {
        self.queue.lock().unwrap().push_back(detection);
    }

    /// Another handle on the same queue and log, for the test to keep.
    pub fn share(&self) -> Self {
        ScriptedDetector {
            queue: self.queue.clone(),
            seen: self.seen.clone(),
            settings: DetectorSettings::default(),
        }
    }
}

impl TargetDetector for ScriptedDetector {
    fn detect(&mut self, frame: &Frame) -> Detection {
        self.seen.lock().unwrap().push(frame.clone());
        self.queue.lock().unwrap().pop_front().unwrap_or_default()
    }

    fn reset_lock(&mut self) {}

    fn settings(&self) -> &DetectorSettings {
        &self.settings
    }

    fn set_settings(&mut self, settings: DetectorSettings) {
        self.settings = settings;
    }
}

/// A found circle of radius 30 px at `(x, y)` with full confidence.
pub fn circle_at(x: f64, y: f64) -> Detection {
    Detection {
        found: true,
        x_px: x,
        y_px: y,
        radius_px: 30.0,
        confidence: 1.0,
        ..Detection::default()
    }
}
