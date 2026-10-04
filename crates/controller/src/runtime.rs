//! Runs a [`Controller`] on its own thread. Commands and device events
//! share one queue, so the controller sees them in arrival order. The
//! thread also wakes for the replay player's deadline and to poll
//! `settings.json`.

use std::sync::Arc;
use std::sync::mpsc::{self, RecvTimeoutError, Sender};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use shottrainer_tracking::capture::ClockFn;

use crate::backends::Backends;
use crate::controller::{Command, Controller, ControllerConfig, ControllerError, Input};
use crate::events::UiSink;
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
        let controller = Controller::new(config, backends, options.clock.clone(), forward, sink)?;
        let thread = std::thread::Builder::new()
            .name("controller".to_owned())
            .spawn(move || run(controller, &receiver, &options))
            .map_err(ControllerError::Thread)?;
        Ok(ControllerHandle {
            sender,
            thread: Some(thread),
        })
    }

    /// Opens the camera and microphone. On macOS the application should
    /// first ask for camera and microphone access on its main thread,
    /// because AVFoundation only shows the prompt there.
    pub fn start(&self) {
        let _ = self.sender.send(Message::Start);
    }

    pub fn send(&self, command: Command) {
        let _ = self.sender.send(Message::Input(Input::Command(command)));
    }

    /// Saves a running recording, stops the devices and joins the thread.
    pub fn shutdown(mut self) {
        self.stop();
    }

    fn stop(&mut self) {
        let _ = self.sender.send(Message::Shutdown);
        if let Some(thread) = self.thread.take()
            && thread.join().is_err()
        {
            log::error!("controller thread panicked");
        }
    }
}

impl Drop for ControllerHandle {
    fn drop(&mut self) {
        self.stop();
    }
}

fn run(mut controller: Controller, receiver: &mpsc::Receiver<Message>, options: &RuntimeOptions) {
    let mut next_poll = Instant::now() + options.poll_interval;
    loop {
        let until_poll = next_poll.saturating_duration_since(Instant::now());
        let timeout = match controller.next_deadline() {
            Some(due) => until(due - (options.clock)()).min(until_poll),
            None => until_poll,
        };
        match receiver.recv_timeout(timeout) {
            Ok(Message::Input(input)) => controller.handle(input),
            Ok(Message::Start) => controller.start(),
            Ok(Message::Shutdown) | Err(RecvTimeoutError::Disconnected) => break,
            Err(RecvTimeoutError::Timeout) => {}
        }
        if Instant::now() >= next_poll {
            controller.poll_settings();
            next_poll = Instant::now() + options.poll_interval;
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
        fn list_cameras(&mut self) -> Vec<(i64, String)> {
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
        wait_for(&running.events, |e| {
            *e == UiEvent::Player(PlayerEvent::Finished)
        });
        wait_for(&running.events, |e| *e == UiEvent::ReplayPlaying(false));
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
}
