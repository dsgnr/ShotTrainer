//! Synthetic devices for running the interface without a camera, a
//! microphone or OpenCV. The camera draws a dark circle that wanders around
//! the frame centre, the detector finds it by its dark pixels, and the
//! microphone reports a quiet level with periodic shots while recording.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

#[path = "fake/aim.rs"]
mod aim;

use shottrainer_audio::models::{ShotDetectorSettings, ShotEvent};
use shottrainer_audio::{AudioEvent, DeviceSelector};
use shottrainer_controller::Backends;
use shottrainer_controller::backends::{
    AudioBackend, AudioHandle, AudioSink, CameraBackend, CameraHandle,
};
use shottrainer_tracking::capture::{
    CameraCapture, CaptureOptions, ClockFn, EventSink, FrameSource, OpenedSource,
};
use shottrainer_tracking::detector::{DetectorSettings, TargetDetector};
use shottrainer_tracking::frame::{Frame, PixelFormat};
use shottrainer_tracking::models::Detection;
use shottrainer_tracking::tuning::HoughScorer;

pub const WIDTH: u32 = 640;
pub const HEIGHT: u32 = 480;
pub const FPS: f64 = 60.0;
pub const CIRCLE_RADIUS_PX: f64 = 15.0;
const BACKGROUND: u8 = 225;
const INK: u8 = 20;
/// Pixels darker than this count as the circle.
const DARK: u8 = 128;
/// Fewer dark pixels than this is no circle.
const MIN_DARK_PIXELS: usize = 50;
const SHOT_EVERY: Duration = Duration::from_secs(10);
const LEVEL_EVERY: Duration = Duration::from_millis(50);
const QUIET_LEVEL: f64 = 0.02;
const SHOT_LEVEL: f64 = 0.8;
const SAMPLE_RATE: u32 = 48_000;

/// The synthetic devices together.
pub fn backends() -> Backends {
    let simulation = Arc::new(Mutex::new(Simulation::default()));
    Backends {
        camera: Box::new(SyntheticCamera {
            simulation: simulation.clone(),
        }),
        audio: Box::new(FakeMicrophone {
            shot_every: Some(SHOT_EVERY),
            simulation,
        }),
        detector: Box::new(DarkSpotDetector::default()),
        scorer: Box::new(NoHoughScorer),
    }
}

#[derive(Default)]
struct Simulation {
    recording: bool,
    started: Option<Instant>,
}

/// The synthetic aim in frame `n`, in camera coordinates.
pub fn circle_centre(n: u64) -> (f64, f64) {
    let (x, y) = aim::position(n as f64 / FPS);
    let mm_per_px = 60.0 / (CIRCLE_RADIUS_PX * 2.0);
    (
        f64::from(WIDTH) / 2.0 - x / mm_per_px,
        f64::from(HEIGHT) / 2.0 - y / mm_per_px,
    )
}

/// A grey frame with a filled dark circle.
pub fn draw_circle(width: u32, height: u32, centre: (f64, f64), radius: f64) -> Option<Frame> {
    let mut data = vec![BACKGROUND; width as usize * height as usize];
    let (cx, cy) = centre;
    let rows =
        (cy - radius).floor().max(0.0) as u32..(cy + radius).ceil().min(f64::from(height)) as u32;
    for y in rows {
        let cols = (cx - radius).floor().max(0.0) as u32
            ..(cx + radius).ceil().min(f64::from(width)) as u32;
        for x in cols {
            let (dx, dy) = (f64::from(x) + 0.5 - cx, f64::from(y) + 0.5 - cy);
            if dx * dx + dy * dy <= radius * radius {
                data[y as usize * width as usize + x as usize] = INK;
            }
        }
    }
    Frame::new(width, height, PixelFormat::Grey, data).ok()
}

struct SyntheticSource {
    simulation: Arc<Mutex<Simulation>>,
}

impl FrameSource for SyntheticSource {
    fn read(&mut self) -> Option<Frame> {
        thread::sleep(Duration::from_secs_f64(1.0 / FPS));
        let mut simulation = self.simulation.lock().unwrap();
        let centre = if simulation.recording {
            let seconds = simulation
                .started
                .get_or_insert_with(Instant::now)
                .elapsed()
                .as_secs_f64();
            circle_centre((seconds * FPS).floor() as u64)
        } else {
            (f64::from(WIDTH) / 2.0, f64::from(HEIGHT) / 2.0)
        };
        draw_circle(WIDTH, HEIGHT, centre, CIRCLE_RADIUS_PX)
    }
}

/// One camera, `Synthetic camera` at index 0. Any index opens it.
#[derive(Default)]
pub struct SyntheticCamera {
    simulation: Arc<Mutex<Simulation>>,
}

impl CameraBackend for SyntheticCamera {
    fn list_cameras(&mut self, _running: Option<i32>) -> Vec<(i64, String)> {
        vec![(0, "Synthetic camera".to_owned())]
    }

    fn start(
        &mut self,
        _device_index: i32,
        clock: ClockFn,
        on_event: EventSink,
    ) -> Box<dyn CameraHandle> {
        let simulation = self.simulation.clone();
        let opener = Box::new(move || {
            Ok(OpenedSource {
                source: Box::new(SyntheticSource { simulation }) as Box<dyn FrameSource>,
                width: WIDTH,
                height: HEIGHT,
                fps: FPS,
            })
        });
        Box::new(CameraCapture::start_with(
            opener,
            CaptureOptions::default(),
            clock,
            on_event,
        ))
    }
}

/// Finds the centroid of the dark pixels and the radius of a disc with the
/// same area. Enough for the synthetic circle, not for a real target.
#[derive(Default)]
pub struct DarkSpotDetector {
    settings: DetectorSettings,
}

impl TargetDetector for DarkSpotDetector {
    fn detect(&mut self, frame: &Frame) -> Detection {
        let width = frame.width() as usize;
        let channels = frame.format().channels();
        let (mut count, mut sum_x, mut sum_y) = (0_usize, 0.0, 0.0);
        for (i, pixel) in frame.data().chunks_exact(channels).enumerate() {
            if pixel[0] < DARK {
                count += 1;
                sum_x += (i % width) as f64 + 0.5;
                sum_y += (i / width) as f64 + 0.5;
            }
        }
        if count < MIN_DARK_PIXELS {
            return Detection::default();
        }
        let radius = (count as f64 / std::f64::consts::PI).sqrt();
        Detection {
            found: true,
            x_px: sum_x / count as f64,
            y_px: sum_y / count as f64,
            radius_px: radius,
            confidence: 1.0,
            semi_major_px: radius,
            semi_minor_px: radius,
            ..Detection::default()
        }
    }

    fn reset_lock(&mut self) {}

    fn settings(&self) -> &DetectorSettings {
        &self.settings
    }

    fn set_settings(&mut self, settings: DetectorSettings) {
        self.settings = settings;
    }
}

/// Auto-optimise finds nothing with the synthetic devices.
pub struct NoHoughScorer;

impl HoughScorer for NoHoughScorer {
    fn hough_score(
        &mut self,
        _adjusted: &Frame,
        _blur: i32,
        _base: &DetectorSettings,
    ) -> Option<f64> {
        None
    }
}

/// A microphone called `default` that reports [`QUIET_LEVEL`] and, when
/// `shot_every` is set, a shot at that interval while recording.
pub struct FakeMicrophone {
    shot_every: Option<Duration>,
    simulation: Arc<Mutex<Simulation>>,
}

impl FakeMicrophone {
    pub fn new(shot_every: Option<Duration>) -> Self {
        FakeMicrophone {
            shot_every,
            simulation: Arc::default(),
        }
    }
}

impl AudioBackend for FakeMicrophone {
    fn list_inputs(&mut self) -> Vec<String> {
        vec!["default".to_owned()]
    }

    fn start(
        &mut self,
        _settings: ShotDetectorSettings,
        _device: DeviceSelector,
        clock: ClockFn,
        on_event: AudioSink,
    ) -> Box<dyn AudioHandle> {
        let running = Arc::new(AtomicBool::new(true));
        let on_event: Arc<AudioSink> = Arc::new(on_event);
        let shot_every = self.shot_every;
        let schedule = Arc::new(Mutex::new((false, Duration::ZERO)));
        let thread = thread::Builder::new()
            .name("fake-microphone".to_owned())
            .spawn({
                let (running, on_event) = (running.clone(), on_event.clone());
                let schedule = schedule.clone();
                let simulation = self.simulation.clone();
                move || {
                    on_event(AudioEvent::Started);
                    while running.load(Ordering::SeqCst) {
                        thread::sleep(LEVEL_EVERY);
                        let mut schedule = schedule.lock().unwrap();
                        let elapsed = simulation
                            .lock()
                            .unwrap()
                            .started
                            .map(|start| start.elapsed())
                            .unwrap_or_default();
                        if schedule.0
                            && shot_every.is_some_and(|every| elapsed >= schedule.1 + every)
                        {
                            schedule.1 += shot_every.unwrap();
                            on_event(AudioEvent::Level(SHOT_LEVEL));
                            on_event(AudioEvent::Shot(ShotEvent {
                                timestamp: clock() - (elapsed - schedule.1).as_secs_f64(),
                                audio_level: SHOT_LEVEL,
                                sample_rate: SAMPLE_RATE,
                            }));
                        } else {
                            on_event(AudioEvent::Level(QUIET_LEVEL));
                        }
                    }
                }
            });
        let thread = match thread {
            Ok(thread) => Some(thread),
            Err(error) => {
                on_event(AudioEvent::Error(format!(
                    "Could not start the fake microphone: {error}"
                )));
                None
            }
        };
        Box::new(FakeMicrophoneHandle {
            simulation: self.simulation.clone(),
            schedule,
            running,
            thread,
            on_event,
        })
    }
}

struct FakeMicrophoneHandle {
    simulation: Arc<Mutex<Simulation>>,
    schedule: Arc<Mutex<(bool, Duration)>>,
    running: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
    on_event: Arc<AudioSink>,
}

impl AudioHandle for FakeMicrophoneHandle {
    fn update_settings(&self, _settings: ShotDetectorSettings) {}

    fn set_recording(&self, recording: bool) {
        let mut schedule = self.schedule.lock().unwrap();
        if schedule.0 != recording {
            *schedule = (recording, Duration::ZERO);
            let mut simulation = self.simulation.lock().unwrap();
            simulation.recording = recording;
            simulation.started = recording.then(Instant::now);
        }
    }

    fn stop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        if let Some(thread) = self.thread.take() {
            if thread.join().is_err() {
                log::error!("fake microphone thread panicked");
            }
            (self.on_event)(AudioEvent::Stopped);
        }
    }
}

impl Drop for FakeMicrophoneHandle {
    fn drop(&mut self) {
        self.stop();
    }
}
#[cfg(test)]
mod tests {
    use std::sync::{Mutex, mpsc};
    use std::time::Instant;

    use shottrainer_tracking::capture::CameraEvent;

    use super::*;

    #[test]
    fn the_detector_finds_a_drawn_circle() {
        let frame = draw_circle(200, 150, (120.25, 70.5), 20.0).unwrap();
        let found = DarkSpotDetector::default().detect(&frame);
        assert!(found.found);
        assert!((found.x_px - 120.25).abs() < 0.5, "{}", found.x_px);
        assert!((found.y_px - 70.5).abs() < 0.5, "{}", found.y_px);
        assert!((found.radius_px - 20.0).abs() < 0.5, "{}", found.radius_px);
    }

    #[test]
    fn the_detector_finds_nothing_in_a_blank_frame() {
        let frame = Frame::filled(64, 48, PixelFormat::Grey, BACKGROUND).unwrap();
        assert!(!DarkSpotDetector::default().detect(&frame).found);
    }

    #[test]
    fn the_detector_ignores_a_few_dark_pixels() {
        let frame = draw_circle(64, 48, (32.0, 24.0), 3.0).unwrap();
        assert!(!DarkSpotDetector::default().detect(&frame).found);
    }

    #[test]
    fn a_circle_partly_outside_the_frame_is_clipped() {
        let frame = draw_circle(100, 100, (-5.0, 50.0), 20.0).unwrap();
        let dark = frame.data().iter().filter(|&&p| p < DARK).count();
        assert!(dark > 0 && dark < 600, "{dark}");
    }

    #[test]
    fn the_circle_wanders_near_the_centre() {
        let centres: Vec<_> = (0..300).map(circle_centre).collect();
        assert_ne!(centres[0], centres[10]);
        for (x, y) in centres {
            assert!(x > CIRCLE_RADIUS_PX && x < f64::from(WIDTH) - CIRCLE_RADIUS_PX);
            assert!(y > CIRCLE_RADIUS_PX && y < f64::from(HEIGHT) - CIRCLE_RADIUS_PX);
        }
    }

    #[test]
    fn the_synthetic_camera_delivers_frames_with_the_circle() {
        let (sender, receiver) = mpsc::channel();
        let sender = Mutex::new(sender);
        let clock: ClockFn = Arc::new(|| 0.0);
        let mut handle = SyntheticCamera::default().start(
            0,
            clock,
            Box::new(move |event| {
                let _ = sender.lock().unwrap().send(event);
            }),
        );
        let deadline = Instant::now() + Duration::from_secs(5);
        let mut frame = None;
        while frame.is_none() {
            let left = deadline.saturating_duration_since(Instant::now());
            match receiver.recv_timeout(left) {
                Ok(CameraEvent::Frame { frame: f, .. }) => frame = Some(f),
                Ok(_) => {}
                Err(_) => panic!("no frame within 5 s"),
            }
        }
        handle.stop();
        let found = DarkSpotDetector::default().detect(&frame.unwrap());
        let (x, y) = (f64::from(WIDTH) / 2.0, f64::from(HEIGHT) / 2.0);
        assert!((found.x_px - x).abs() < 0.5 && (found.y_px - y).abs() < 0.5);
        assert!((found.radius_px - CIRCLE_RADIUS_PX).abs() < 0.5);
    }

    fn collect_audio(
        shot_every: Option<Duration>,
        until: impl Fn(&[AudioEvent]) -> bool,
    ) -> Vec<AudioEvent> {
        let (sender, receiver) = mpsc::channel();
        let sender = Mutex::new(sender);
        let clock: ClockFn = Arc::new(|| 42.0);
        let mut handle = FakeMicrophone::new(shot_every).start(
            ShotDetectorSettings::default(),
            DeviceSelector::Default,
            clock,
            Box::new(move |event| {
                let _ = sender.lock().unwrap().send(event);
            }),
        );
        handle.set_recording(true);
        let deadline = Instant::now() + Duration::from_secs(5);
        let mut events = Vec::new();
        while !until(&events) {
            let left = deadline.saturating_duration_since(Instant::now());
            match receiver.recv_timeout(left) {
                Ok(event) => events.push(event),
                Err(_) => panic!("timed out with {events:?}"),
            }
        }
        handle.stop();
        events.extend(receiver.try_iter());
        events
    }

    #[test]
    fn the_microphone_starts_reports_levels_and_stops() {
        let events = collect_audio(None, |events| events.len() >= 3);
        assert_eq!(events.first(), Some(&AudioEvent::Started));
        assert_eq!(events[1], AudioEvent::Level(QUIET_LEVEL));
        assert_eq!(events.last(), Some(&AudioEvent::Stopped));
        assert!(!events.iter().any(|e| matches!(e, AudioEvent::Shot(_))));
    }

    #[test]
    fn the_microphone_fires_shots_at_the_interval() {
        let events = collect_audio(Some(Duration::from_millis(100)), |events| {
            events.iter().any(|e| matches!(e, AudioEvent::Shot(_)))
        });
        let shot = events
            .iter()
            .position(|e| matches!(e, AudioEvent::Shot(_)))
            .unwrap();
        assert_eq!(events[shot - 1], AudioEvent::Level(SHOT_LEVEL));
        let AudioEvent::Shot(event) = &events[shot] else {
            unreachable!()
        };
        assert!((41.0..=42.0).contains(&event.timestamp));
        assert_eq!(event.audio_level, SHOT_LEVEL);
        assert_eq!(event.sample_rate, SAMPLE_RATE);
    }
    #[test]
    fn automatic_microphone_shots_wait_for_recording_and_reset_after_stop() {
        let (sender, receiver) = mpsc::channel();
        let mut handle = FakeMicrophone::new(Some(Duration::from_millis(200))).start(
            ShotDetectorSettings::default(),
            DeviceSelector::Default,
            Arc::new(|| 42.0),
            Box::new(move |event| {
                sender.send(event).unwrap();
            }),
        );
        assert_eq!(
            receiver.recv_timeout(Duration::from_secs(2)).unwrap(),
            AudioEvent::Started
        );
        for _ in 0..6 {
            assert_eq!(
                receiver.recv_timeout(Duration::from_secs(2)).unwrap(),
                AudioEvent::Level(QUIET_LEVEL)
            );
        }
        for _ in 0..2 {
            handle.set_recording(true);
            for _ in 0..3 {
                assert_eq!(
                    receiver.recv_timeout(Duration::from_secs(2)).unwrap(),
                    AudioEvent::Level(QUIET_LEVEL)
                );
            }
            assert_eq!(
                receiver.recv_timeout(Duration::from_secs(2)).unwrap(),
                AudioEvent::Level(SHOT_LEVEL)
            );
            assert!(matches!(
                receiver.recv_timeout(Duration::from_secs(2)).unwrap(),
                AudioEvent::Shot(_)
            ));
            handle.set_recording(false);
            for _ in 0..6 {
                assert_eq!(
                    receiver.recv_timeout(Duration::from_secs(2)).unwrap(),
                    AudioEvent::Level(QUIET_LEVEL)
                );
            }
        }
        handle.stop();
    }
    #[test]
    fn tracked_dev_approaches_settle_within_a_compact_area() {
        let mut tracker =
            shottrainer_tracking::tracker::Tracker::new(60.0, DarkSpotDetector::default()).unwrap();
        let mut samples = Vec::new();
        for n in 0..=599 {
            let frame = draw_circle(WIDTH, HEIGHT, circle_centre(n), CIRCLE_RADIUS_PX).unwrap();
            samples.push(tracker.process(&frame, n as f64 / FPS, None).unwrap());
        }
        assert!((25.0..80.0).contains(&samples[0].y_mm.unwrap()));
        assert!((-85.0..-60.0).contains(&samples[0].x_mm.unwrap()));
        let last = samples.last().unwrap();
        assert!(last.x_mm.unwrap().hypot(last.y_mm.unwrap()) < 6.0);
        assert!(samples[0].y_mm.unwrap() > last.y_mm.unwrap() + 20.0);
    }

    #[test]
    fn slow_camera_updates_follow_elapsed_recording_time() {
        let simulation = Arc::new(Mutex::new(Simulation {
            recording: true,
            started: Some(Instant::now() - Duration::from_millis(9900)),
        }));
        let mut source = SyntheticSource { simulation };
        let detection = DarkSpotDetector::default().detect(&source.read().unwrap());
        assert!((detection.x_px - 320.0).hypot(detection.y_px - 240.0) < 16.0);
    }

    #[test]
    fn the_synthetic_camera_moves_only_during_recording() {
        let simulation = Arc::new(Mutex::new(Simulation::default()));
        let mut source = SyntheticSource {
            simulation: simulation.clone(),
        };
        let mut detector = DarkSpotDetector::default();
        let idle = detector.detect(&source.read().unwrap());
        let still = detector.detect(&source.read().unwrap());
        assert_eq!((idle.x_px, idle.y_px), (still.x_px, still.y_px));
        simulation.lock().unwrap().recording = true;
        let moving = detector.detect(&source.read().unwrap());
        assert!((moving.x_px - idle.x_px).hypot(moving.y_px - idle.y_px) > 2.0);
        simulation.lock().unwrap().recording = false;
        let stopped = detector.detect(&source.read().unwrap());
        assert_eq!((idle.x_px, idle.y_px), (stopped.x_px, stopped.y_px));
    }
}
