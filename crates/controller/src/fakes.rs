//! Test doubles for the hardware and OpenCV boundaries.

use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

use shottrainer_audio::models::ShotDetectorSettings;
use shottrainer_audio::{AudioEvent, DeviceSelector};
use shottrainer_tracking::capture::{CameraEvent, ClockFn, EventSink};
use shottrainer_tracking::detector::{DetectorSettings, TargetDetector};
use shottrainer_tracking::frame::Frame;
use shottrainer_tracking::models::Detection;

use crate::backends::{AudioBackend, AudioHandle, AudioSink, CameraBackend, CameraHandle};

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

#[derive(Default)]
pub struct CameraState {
    pub cameras: Vec<(i64, String)>,
    pub lists: usize,
    pub started: Vec<i32>,
    pub stopped: usize,
    pub sinks: Vec<Arc<EventSink>>,
}

/// Records calls and keeps each capture's event sink for the test to drive.
#[derive(Clone, Default)]
pub struct FakeCamera(pub Arc<Mutex<CameraState>>);

impl FakeCamera {
    pub fn with_cameras(cameras: &[(i64, &str)]) -> Self {
        let fake = FakeCamera::default();
        fake.state().cameras = cameras.iter().map(|(i, n)| (*i, (*n).to_owned())).collect();
        fake
    }

    pub fn state(&self) -> std::sync::MutexGuard<'_, CameraState> {
        self.0.lock().unwrap()
    }

    /// Sends `event` through the sink of the `start`th capture.
    pub fn emit(&self, start: usize, event: CameraEvent) {
        let sink = self.state().sinks[start].clone();
        sink(event);
    }
}

struct FakeCameraHandle(Arc<Mutex<CameraState>>);

impl CameraHandle for FakeCameraHandle {
    fn stop(&mut self) {
        self.0.lock().unwrap().stopped += 1;
    }
}

impl CameraBackend for FakeCamera {
    fn list_cameras(&mut self) -> Vec<(i64, String)> {
        let mut state = self.state();
        state.lists += 1;
        state.cameras.clone()
    }

    fn start(
        &mut self,
        device_index: i32,
        _clock: ClockFn,
        on_event: EventSink,
    ) -> Box<dyn CameraHandle> {
        let mut state = self.state();
        state.started.push(device_index);
        state.sinks.push(Arc::new(on_event));
        Box::new(FakeCameraHandle(self.0.clone()))
    }
}

#[derive(Default)]
pub struct AudioState {
    pub inputs: Vec<String>,
    pub started: Vec<DeviceSelector>,
    pub start_settings: Vec<ShotDetectorSettings>,
    pub updates: Vec<ShotDetectorSettings>,
    pub stopped: usize,
    pub sinks: Vec<Arc<AudioSink>>,
}

#[derive(Clone, Default)]
pub struct FakeAudio(pub Arc<Mutex<AudioState>>);

impl FakeAudio {
    pub fn state(&self) -> std::sync::MutexGuard<'_, AudioState> {
        self.0.lock().unwrap()
    }

    pub fn emit(&self, start: usize, event: AudioEvent) {
        let sink = self.state().sinks[start].clone();
        sink(event);
    }
}

struct FakeAudioHandle(Arc<Mutex<AudioState>>);

impl AudioHandle for FakeAudioHandle {
    fn update_settings(&self, settings: ShotDetectorSettings) {
        self.0.lock().unwrap().updates.push(settings);
    }

    fn stop(&mut self) {
        self.0.lock().unwrap().stopped += 1;
    }
}

impl AudioBackend for FakeAudio {
    fn list_inputs(&mut self) -> Vec<String> {
        self.state().inputs.clone()
    }

    fn start(
        &mut self,
        settings: ShotDetectorSettings,
        device: DeviceSelector,
        _clock: ClockFn,
        on_event: AudioSink,
    ) -> Box<dyn AudioHandle> {
        let mut state = self.state();
        state.started.push(device);
        state.start_settings.push(settings);
        state.sinks.push(Arc::new(on_event));
        Box::new(FakeAudioHandle(self.0.clone()))
    }
}
