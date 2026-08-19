//! The hardware and OpenCV boundaries. The controller only sees these
//! traits, so it is tested with fakes and needs no device or OpenCV.

use shottrainer_audio::models::ShotDetectorSettings;
use shottrainer_audio::{AudioEvent, AudioInput, DeviceSelector, list_audio_inputs};
use shottrainer_tracking::capture::{CameraCapture, ClockFn, EventSink};
use shottrainer_tracking::detector::TargetDetector;
use shottrainer_tracking::tuning::HoughScorer;

/// A running camera. Dropping it stops the capture.
pub trait CameraHandle: Send {
    fn stop(&mut self);
}

impl CameraHandle for CameraCapture {
    fn stop(&mut self) {
        CameraCapture::stop(self);
    }
}

pub trait CameraBackend: Send {
    /// `(index, name)` for every attached camera. May be slow.
    fn list_cameras(&mut self) -> Vec<(i64, String)>;
    /// Starts capturing without blocking. Events arrive on `on_event` from
    /// the capture thread.
    fn start(
        &mut self,
        device_index: i32,
        clock: ClockFn,
        on_event: EventSink,
    ) -> Box<dyn CameraHandle>;
}

pub type AudioSink = Box<dyn Fn(AudioEvent) + Send + Sync + 'static>;

/// A running microphone stream. Dropping it stops the stream.
pub trait AudioHandle: Send {
    fn update_settings(&self, settings: ShotDetectorSettings);
    fn stop(&mut self);
}

impl AudioHandle for AudioInput {
    fn update_settings(&self, settings: ShotDetectorSettings) {
        AudioInput::update_settings(self, settings);
    }

    fn stop(&mut self) {
        AudioInput::stop(self);
    }
}

pub trait AudioBackend: Send {
    /// Device names led by `"default"`.
    fn list_inputs(&mut self) -> Vec<String>;
    fn start(
        &mut self,
        settings: ShotDetectorSettings,
        device: DeviceSelector,
        clock: ClockFn,
        on_event: AudioSink,
    ) -> Box<dyn AudioHandle>;
}

/// The microphone through `cpal`.
pub struct CpalAudio;

impl AudioBackend for CpalAudio {
    fn list_inputs(&mut self) -> Vec<String> {
        list_audio_inputs()
    }

    fn start(
        &mut self,
        settings: ShotDetectorSettings,
        device: DeviceSelector,
        clock: ClockFn,
        on_event: AudioSink,
    ) -> Box<dyn AudioHandle> {
        Box::new(AudioInput::start(settings, device, clock, on_event))
    }
}

/// Everything the controller needs from outside the workspace's pure code.
pub struct Backends {
    pub camera: Box<dyn CameraBackend>,
    pub audio: Box<dyn AudioBackend>,
    pub detector: Box<dyn TargetDetector>,
    pub scorer: Box<dyn HoughScorer + Send>,
}
