//! Runs a [`Controller`] on its own thread. Commands and device events
//! share one queue, so the controller sees them in arrival order. The
//! thread also wakes for the replay player's deadline and to poll
//! `settings.json`.

use std::panic::{AssertUnwindSafe, catch_unwind};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use shottrainer_tracking::capture::ClockFn;

use crate::backends::Backends;
use crate::controller::{Command, Controller, ControllerConfig, ControllerError, Input};
use crate::events::{UiEvent, UiSink};
use crate::watcher::POLL_INTERVAL;

/// Seconds since this clock was created. Frame and shot timestamps share it.
pub fn monotonic_clock() -> ClockFn {
    let origin = Instant::now();
    Arc::new(move || origin.elapsed().as_secs_f64())
}

pub struct RuntimeOptions {
    pub clock: ClockFn,
    /// How often `settings.json` is checked for outside edits.
    pub poll_interval: Duration,
}

impl Default for RuntimeOptions {
    fn default() -> Self {
        RuntimeOptions {
            clock: monotonic_clock(),
            poll_interval: POLL_INTERVAL,
        }
    }
}

enum Message {
    Input(Input),
    Start,
    Shutdown,
}

/// The front end's connection to a running controller. Dropping it shuts
/// the controller down.
pub struct ControllerHandle {
    sender: Sender<Message>,
    thread: Option<JoinHandle<()>>,
    running: Arc<AtomicBool>,
}

impl ControllerHandle {
    /// Loads everything on the caller's thread, so a database that cannot
    /// be opened is reported here, then moves the controller to its own
    /// thread. `sink` is called on that thread.
    pub fn spawn(
        config: ControllerConfig,
        backends: Backends,
        options: RuntimeOptions,
        sink: UiSink,
    ) -> Result<Self, ControllerError> {
        let (sender, receiver) = mpsc::channel();
        let forward = {
            let sender = sender.clone();
            Arc::new(move |event| {
                let _ = sender.send(Message::Input(Input::Device(event)));
            })
        };
        // The controller owns the sink, so a copy is kept to report a panic.
        let sink = Arc::new(Mutex::new(sink));
        let controller_sink: UiSink = {
            let sink = sink.clone();
            Box::new(move |event| call_sink(&sink, event))
        };
        let controller = Controller::new(
            config,
            backends,
            options.clock.clone(),
            forward,
            controller_sink,
        )?;
        let running = Arc::new(AtomicBool::new(true));
        let thread = thread::Builder::new()
            .name("controller".to_owned())
            .spawn({
                let running = running.clone();
                move || {
                    let outcome =
                        catch_unwind(AssertUnwindSafe(|| run(controller, &receiver, &options)));
                    running.store(false, Ordering::SeqCst);
                    if let Err(payload) = outcome {
                        let reason = panic_text(payload.as_ref());
                        log::error!("controller thread panicked: {reason}");
                        call_sink(&sink, UiEvent::ControllerFailed(reason));
                    }
                }
            })
            .map_err(ControllerError::Thread)?;
        Ok(ControllerHandle {
            sender,
            thread: Some(thread),
            running,
        })
    }

    /// Opens the camera and microphone. On macOS the application should
    /// first ask for camera and microphone access on its main thread,
    /// because AVFoundation only shows the prompt there.
    pub fn start(&self) {
        let _ = self.sender.send(Message::Start);
    }

    /// False once the controller thread has ended, after a shutdown or a
    /// panic. A panic is also reported as [`UiEvent::ControllerFailed`].
    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }

    pub fn send(&self, command: Command) {
        let _ = self.sender.send(Message::Input(Input::Command(command)));
    }

    /// Saves a running recording, stops the devices and joins the thread.
    /// Must not be called from the sink, which runs on that thread. The
    /// join is skipped there.
    pub fn shutdown(mut self) {
        self.stop();
    }

    fn stop(&mut self) {
        let _ = self.sender.send(Message::Shutdown);
        if let Some(thread) = self.thread.take()
            && thread.thread().id() != thread::current().id()
        {
            let _ = thread.join();
        }
    }
}

impl Drop for ControllerHandle {
    fn drop(&mut self) {
        self.stop();
    }
}

/// A panic in the sink itself is swallowed, because this also runs while
/// reporting a panic.
fn call_sink(sink: &Mutex<UiSink>, event: UiEvent) {
    let sink = sink
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner);
    let _ = catch_unwind(AssertUnwindSafe(|| sink(event)));
}

fn panic_text(payload: &(dyn std::any::Any + Send)) -> String {
    payload
        .downcast_ref::<&str>()
        .map(|text| (*text).to_owned())
        .or_else(|| payload.downcast_ref::<String>().cloned())
        .unwrap_or_else(|| "unknown panic".to_owned())
}

/// When `settings.json` is next checked.
struct PollSchedule {
    next: Instant,
    interval: Duration,
}

impl PollSchedule {
    fn new(now: Instant, interval: Duration) -> Self {
        PollSchedule {
            next: now + interval,
            interval,
        }
    }

    /// How long to block for a message. `deadline_in` is the seconds until
    /// the replay deadline, if there is one.
    fn wait(&self, now: Instant, deadline_in: Option<f64>) -> Duration {
        let until_poll = self.next.saturating_duration_since(now);
        match deadline_in {
            Some(seconds) => until(seconds).min(until_poll),
            None => until_poll,
        }
    }

    /// True when a check is due, and schedules the next one a full
    /// interval after `now`.
    fn due(&mut self, now: Instant) -> bool {
        if now < self.next {
            return false;
        }
        self.next = now + self.interval;
        true
    }
}

fn run(mut controller: Controller, receiver: &mpsc::Receiver<Message>, options: &RuntimeOptions) {
    let mut schedule = PollSchedule::new(Instant::now(), options.poll_interval);
    loop {
        let deadline_in = controller
            .next_deadline()
            .map(|due| due - (options.clock)());
        match receiver.recv_timeout(schedule.wait(Instant::now(), deadline_in)) {
            Ok(Message::Input(input)) => controller.handle(input),
            Ok(Message::Start) => controller.start(),
            Ok(Message::Shutdown) | Err(RecvTimeoutError::Disconnected) => break,
            Err(RecvTimeoutError::Timeout) => {}
        }
        if schedule.due(Instant::now()) {
            controller.poll_settings();
        }
        if controller
            .next_deadline()
            .is_some_and(|due| (options.clock)() >= due)
        {
            controller.tick();
        }
    }
    controller.shutdown();
}

/// A wait of `seconds`, zero when it is negative and the poll interval
/// when it is not a finite number, so a bad deadline cannot spin the loop.
fn until(seconds: f64) -> Duration {
    if seconds.is_nan() {
        return POLL_INTERVAL;
    }
    Duration::try_from_secs_f64(seconds.max(0.0)).unwrap_or(POLL_INTERVAL)
}

#[cfg(test)]
mod tests {
    use std::cell::Cell;
    use std::sync::Mutex;
    use std::sync::atomic::{AtomicBool, Ordering};

    use shottrainer_core::sessions::{NewShot, SessionRepository, make_engine};
    use shottrainer_settings::{Preferences, save_preferences};
    use shottrainer_tracking::capture::{
        CameraCapture, CaptureOptions, EventSink, FrameSource, OpenedSource,
    };
    use shottrainer_tracking::frame::{Frame, PixelFormat};
    use shottrainer_tracking::models::TrackingSample;

    use super::*;
    use crate::backends::{CameraBackend, CameraHandle};
    use crate::events::UiEvent;
    use crate::fakes::FakeCamera;
    use crate::fakes::{FakeAudio, FixedScorer, ScriptedDetector, circle_at};
    use crate::frames::TrackingStatus;
    use crate::paths::DataPaths;
    use crate::player::PlayerEvent;

    const WAIT: Duration = Duration::from_secs(5);

    /// A blank frame every 5 ms until dropped.
    struct BlankSource(Arc<AtomicBool>);

    impl FrameSource for BlankSource {
        fn read(&mut self) -> Option<Frame> {
            std::thread::sleep(Duration::from_millis(5));
            Frame::filled(640, 480, PixelFormat::Grey, 0).ok()
        }
    }

    impl Drop for BlankSource {
        fn drop(&mut self) {
            self.0.store(true, Ordering::SeqCst);
        }
    }

    /// The real capture thread over a blank source.
    struct ThreadCamera {
        released: Arc<AtomicBool>,
    }

    impl CameraBackend for ThreadCamera {
        fn list_cameras(&mut self, _running: Option<i32>) -> Vec<(i64, String)> {
            vec![(0, "Test".into())]
        }

        fn start(
            &mut self,
            _index: i32,
            clock: ClockFn,
            on_event: EventSink,
        ) -> Box<dyn CameraHandle> {
            let released = self.released.clone();
            Box::new(CameraCapture::start_with(
                Box::new(move || {
                    Ok(OpenedSource {
                        source: Box::new(BlankSource(released)),
                        width: 640,
                        height: 480,
                        fps: 200.0,
                    })
                }),
                CaptureOptions::default(),
                clock,
                on_event,
            ))
        }
    }

    struct Running {
        handle: ControllerHandle,
        events: mpsc::Receiver<UiEvent>,
        released: Arc<AtomicBool>,
        audio: FakeAudio,
        _dir: tempfile::TempDir,
    }

    fn spawn(prepare: impl FnOnce(&DataPaths), poll_interval: Duration) -> Running {
        let dir = tempfile::tempdir().unwrap();
        let paths = DataPaths::in_dir(dir.path());
        prepare(&paths);
        let released = Arc::new(AtomicBool::new(false));
        let detector = ScriptedDetector::default();
        for _ in 0..1000 {
            detector.push(circle_at(320.0, 240.0));
        }
        let audio = FakeAudio::default();
        let backends = Backends {
            camera: Box::new(ThreadCamera {
                released: released.clone(),
            }),
            audio: Box::new(audio.clone()),
            detector: Box::new(detector),
            scorer: Box::new(FixedScorer::default()),
        };
        let (sender, events) = mpsc::channel();
        let sender = Mutex::new(sender);
        let handle = ControllerHandle::spawn(
            ControllerConfig {
                paths,
                app_version: "1".into(),
            },
            backends,
            RuntimeOptions {
                clock: monotonic_clock(),
                poll_interval,
            },
            Box::new(move |event| {
                let _ = sender.lock().unwrap().send(event);
            }),
        )
        .unwrap();
        Running {
            handle,
            events,
            released,
            audio,
            _dir: dir,
        }
    }

    /// Waits for the first event `want` accepts, failing after `WAIT`.
    fn wait_for(events: &mpsc::Receiver<UiEvent>, want: impl Fn(&UiEvent) -> bool) -> UiEvent {
        let deadline = Instant::now() + WAIT;
        loop {
            let left = deadline.saturating_duration_since(Instant::now());
            match events.recv_timeout(left) {
                Ok(event) if want(&event) => return event,
                Ok(_) => {}
                Err(error) => panic!("no matching event within {WAIT:?}: {error}"),
            }
        }
    }

    #[test]
    fn frames_from_a_real_capture_thread_are_tracked() {
        let running = spawn(|_| {}, POLL_INTERVAL);
        running.handle.start();
        wait_for(
            &running.events,
            |e| matches!(e, UiEvent::Frame(view) if view.status == TrackingStatus::Tracking),
        );
        running.handle.shutdown();
        assert!(
            running.released.load(Ordering::SeqCst),
            "the camera was released"
        );
        assert_eq!(running.audio.state().stopped, 1);
    }

    #[test]
    fn dropping_the_handle_shuts_down() {
        let running = spawn(|_| {}, POLL_INTERVAL);
        running.handle.start();
        wait_for(&running.events, |e| matches!(e, UiEvent::Frame(_)));
        drop(running.handle);
        assert!(running.released.load(Ordering::SeqCst));
    }

    #[test]
    fn replay_plays_to_the_end_without_further_commands() {
        let mut session = 0;
        let running = spawn(
            |paths| {
                let db = make_engine(paths.sessions_db.to_str().unwrap()).unwrap();
                let repo = SessionRepository::new(&db);
                session = repo.create_session(&Default::default()).unwrap();
                repo.add_shot(
                    session,
                    &NewShot {
                        ts: 1.0,
                        x_mm: Some(0.0),
                        y_mm: Some(0.0),
                        audio_level: 0.5,
                        confidence: 1.0,
                        score: String::new(),
                    },
                )
                .unwrap();
                let samples: Vec<TrackingSample> = (0..5)
                    .map(|i| TrackingSample {
                        x_mm: Some(0.0),
                        y_mm: Some(0.0),
                        ..TrackingSample::new(0.98 + 0.01 * f64::from(i), 0.0, 0.0)
                    })
                    .collect();
                repo.append_trace(session, &samples).unwrap();
            },
            POLL_INTERVAL,
        );
        running.handle.send(Command::OpenSession(session));
        running.handle.send(Command::SelectShot(0));
        running.handle.send(Command::ReplayPlay);
        let finished = Cell::new(false);
        wait_for(&running.events, |e| {
            if *e == UiEvent::Player(PlayerEvent::Finished) {
                finished.set(true);
            }
            finished.get() && *e == UiEvent::ReplayPlaying(false)
        });
    }

    #[test]
    fn outside_settings_edits_are_picked_up() {
        let running = spawn(|_| {}, Duration::from_millis(20));
        let settings = DataPaths::in_dir(running._dir.path()).settings;
        save_preferences(
            &Preferences {
                circle_diameter_mm: 80.0,
                ..Preferences::default()
            },
            &settings,
        )
        .unwrap();
        let event = wait_for(
            &running.events,
            |e| matches!(e, UiEvent::Preferences { prefs, .. } if prefs.circle_diameter_mm == 80.0),
        );
        assert!(matches!(event, UiEvent::Preferences { .. }));
    }

    #[test]
    fn waits_are_never_negative_or_unbounded() {
        assert_eq!(until(-1.0), Duration::ZERO);
        assert_eq!(until(f64::NAN), POLL_INTERVAL);
        assert_eq!(until(f64::INFINITY), POLL_INTERVAL);
        assert_eq!(until(0.25), Duration::from_millis(250));
    }

    /// Spawns over the given backends with a recording sink.
    fn spawn_with(
        camera: Box<dyn CameraBackend>,
        audio: FakeAudio,
    ) -> (ControllerHandle, mpsc::Receiver<UiEvent>, tempfile::TempDir) {
        let dir = tempfile::tempdir().unwrap();
        let backends = Backends {
            camera,
            audio: Box::new(audio),
            detector: Box::new(ScriptedDetector::default()),
            scorer: Box::new(FixedScorer::default()),
        };
        let (sender, events) = mpsc::channel();
        let sender = Mutex::new(sender);
        let handle = ControllerHandle::spawn(
            ControllerConfig {
                paths: DataPaths::in_dir(dir.path()),
                app_version: "1".into(),
            },
            backends,
            RuntimeOptions::default(),
            Box::new(move |event| {
                let _ = sender.lock().unwrap().send(event);
            }),
        )
        .unwrap();
        (handle, events, dir)
    }

    /// Waits until `condition` holds, failing after `WAIT`.
    fn wait_until(what: &str, condition: impl Fn() -> bool) {
        let deadline = Instant::now() + WAIT;
        while !condition() {
            assert!(Instant::now() < deadline, "timed out waiting for {what}");
            std::thread::sleep(Duration::from_millis(2));
        }
    }

    #[test]
    fn spawn_opens_no_device_until_start() {
        let camera = FakeCamera::with_cameras(&[(0, "Test")]);
        let audio = FakeAudio::default();
        let (handle, events, _dir) = spawn_with(Box::new(camera.clone()), audio.clone());
        // A command's reply proves the thread is running and has drained
        // everything sent before it.
        handle.send(Command::ListSessions);
        wait_for(&events, |e| matches!(e, UiEvent::Sessions(_)));
        assert!(camera.state().started.is_empty(), "camera opened by spawn");
        assert!(
            audio.state().started.is_empty(),
            "microphone opened by spawn"
        );

        handle.start();
        wait_until("both devices to open", || {
            !camera.state().started.is_empty() && !audio.state().started.is_empty()
        });
        handle.shutdown();
    }

    struct PanickingCamera;

    impl CameraBackend for PanickingCamera {
        fn list_cameras(&mut self, _running: Option<i32>) -> Vec<(i64, String)> {
            vec![(0, "Test".into())]
        }

        fn start(&mut self, _: i32, _: ClockFn, _: EventSink) -> Box<dyn CameraHandle> {
            panic!("camera backend failed");
        }
    }

    #[test]
    fn a_panic_on_the_controller_thread_is_reported() {
        let (handle, events, _dir) = spawn_with(Box::new(PanickingCamera), FakeAudio::default());
        assert!(handle.is_running());
        handle.start();
        let event = wait_for(&events, |e| matches!(e, UiEvent::ControllerFailed(_)));
        assert_eq!(
            event,
            UiEvent::ControllerFailed("camera backend failed".into())
        );
        wait_until("the handle to report the thread ended", || {
            !handle.is_running()
        });
    }

    #[test]
    fn is_running_is_false_after_the_thread_exits_normally() {
        let (handle, _events, _dir) =
            spawn_with(Box::new(FakeCamera::default()), FakeAudio::default());
        assert!(handle.is_running());
        let running = handle.running.clone();
        handle.shutdown();
        assert!(!running.load(Ordering::SeqCst));
    }

    fn schedule(interval_ms: u64) -> (Instant, PollSchedule) {
        let now = Instant::now();
        (
            now,
            PollSchedule::new(now, Duration::from_millis(interval_ms)),
        )
    }

    #[test]
    fn a_far_replay_deadline_does_not_delay_the_settings_poll() {
        let (now, schedule) = schedule(20);
        assert_eq!(schedule.wait(now, Some(10.0)), Duration::from_millis(20));
    }

    #[test]
    fn a_near_replay_deadline_wakes_before_the_poll() {
        let (now, schedule) = schedule(20);
        assert_eq!(schedule.wait(now, Some(0.005)), Duration::from_millis(5));
    }

    #[test]
    fn the_next_poll_is_a_full_interval_after_the_last() {
        let (now, mut schedule) = schedule(20);
        let at = now + Duration::from_millis(25);
        assert!(schedule.due(at));
        assert_eq!(schedule.wait(at, None), Duration::from_millis(20));
        assert!(!schedule.due(at), "a poll is not due twice");
        assert!(!schedule.due(at + Duration::from_millis(19)));
        assert!(schedule.due(at + Duration::from_millis(20)));
    }

    #[test]
    fn a_poll_is_not_due_early() {
        let (now, mut schedule) = schedule(20);
        assert!(!schedule.due(now + Duration::from_millis(19)));
    }

    #[test]
    fn unusable_deadlines_neither_spin_nor_panic() {
        let (now, schedule) = schedule(20);
        assert_eq!(
            schedule.wait(now, Some(f64::NAN)),
            Duration::from_millis(20)
        );
        assert_eq!(
            schedule.wait(now, Some(f64::INFINITY)),
            Duration::from_millis(20)
        );
        assert_eq!(schedule.wait(now, Some(-3.0)), Duration::ZERO);
        assert_eq!(schedule.wait(now, None), Duration::from_millis(20));
    }
}
