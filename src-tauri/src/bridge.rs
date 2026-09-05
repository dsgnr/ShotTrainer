//! Connects one controller to the webview. Controller events become
//! [`WireEvent`] values on an [`Outlet`], frame pixels go to the frame
//! channel, and commands are refused once the controller thread has ended.

use std::sync::{Arc, Mutex, MutexGuard, PoisonError};

use serde::Serialize;
use shottrainer_controller::{
    Backends, Command, ControllerConfig, ControllerHandle, RuntimeOptions, UiEvent, UiSink,
};

use crate::mode::DeviceMode;
use crate::wire::WireEvent;

/// What `send` returns once the controller thread has ended.
pub const STOPPED: &str = "The controller has stopped. Restart it to continue.";

/// Where the bridge delivers to. The Tauri implementation emits events and
/// writes to the frame channel. Both methods are called on the controller
/// thread, and during start-up on the thread that spawns it.
pub trait Outlet: Send + Sync + 'static {
    fn emit(&self, event: &WireEvent);
    /// False when no frame channel is subscribed or the send failed.
    fn send_pixels(&self, packet: Vec<u8>) -> bool;
}

/// Builds a fresh set of devices for each controller, so a restart opens
/// them again.
pub type BackendFactory = Arc<dyn Fn() -> Backends + Send + Sync>;

pub struct ShellConfig {
    pub controller: ControllerConfig,
    pub backends: BackendFactory,
    pub mode: DeviceMode,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ShellStatus {
    pub running: bool,
    /// Why the controller could not be created, such as a database that
    /// cannot be opened.
    pub error: Option<String>,
    pub fake_devices: bool,
    /// `camera` or `microphone` for each access the user refused.
    pub denied: Vec<String>,
}

struct Shared<O> {
    outlet: O,
}

impl<O: Outlet> Shared<O> {
    fn deliver(&self, event: UiEvent) {
        self.outlet.emit(&WireEvent::from(&event));
    }
}

enum Slot {
    Empty,
    Running(ControllerHandle),
    Failed(String),
}

pub struct Bridge<O: Outlet> {
    shared: Arc<Shared<O>>,
    config: ShellConfig,
    slot: Mutex<Slot>,
    denied: Mutex<Vec<String>>,
}

impl<O: Outlet> Bridge<O> {
    pub fn new(outlet: O, config: ShellConfig) -> Self {
        Bridge {
            shared: Arc::new(Shared { outlet }),
            config,
            slot: Mutex::new(Slot::Empty),
            denied: Mutex::new(Vec::new()),
        }
    }

    pub fn outlet(&self) -> &O {
        &self.shared.outlet
    }

    /// Creates the controller without opening any device. A failure is kept
    /// for [`Bridge::status`] and returned to every later `send`.
    pub fn spawn(&self) -> Result<(), String> {
        let mut slot = self.slot();
        *slot = self.new_controller();
        match &*slot {
            Slot::Failed(error) => Err(error.clone()),
            _ => Ok(()),
        }
    }

    fn new_controller(&self) -> Slot {
        let shared = self.shared.clone();
        let sink: UiSink = Box::new(move |event| shared.deliver(event));
        match ControllerHandle::spawn(
            self.config.controller.clone(),
            (self.config.backends)(),
            RuntimeOptions::default(),
            sink,
        ) {
            Ok(handle) => Slot::Running(handle),
            Err(error) => {
                log::error!("{error}");
                Slot::Failed(error.to_string())
            }
        }
    }

    /// Opens the camera and microphone. Called once device access is
    /// settled.
    pub fn start(&self) {
        if let Slot::Running(handle) = &*self.slot() {
            handle.start();
        }
    }

    /// The webview is listening, so the state it missed is sent again.
    pub fn ready(&self) -> Result<(), String> {
        self.send(Command::Refresh)
    }

    pub fn send(&self, command: Command) -> Result<(), String> {
        match &*self.slot() {
            Slot::Running(handle) if handle.is_running() => {
                handle.send(command);
                Ok(())
            }
            Slot::Failed(error) => Err(error.clone()),
            _ => Err(STOPPED.to_owned()),
        }
    }

    /// Saves a running recording and stops the controller thread.
    pub fn shutdown(&self) {
        if let Slot::Running(handle) = std::mem::replace(&mut *self.slot(), Slot::Empty) {
            handle.shutdown();
        }
    }

    pub fn status(&self) -> ShellStatus {
        let (running, error) = match &*self.slot() {
            Slot::Running(handle) => (handle.is_running(), None),
            Slot::Failed(error) => (false, Some(error.clone())),
            Slot::Empty => (false, None),
        };
        ShellStatus {
            running,
            error,
            fake_devices: self.config.mode == DeviceMode::Fake,
            denied: self
                .denied
                .lock()
                .unwrap_or_else(PoisonError::into_inner)
                .clone(),
        }
    }

    pub fn access_denied(&self, media: &str) {
        log::warn!("Access to the {media} was refused");
        self.denied
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(media.to_owned());
    }

    fn slot(&self) -> MutexGuard<'_, Slot> {
        self.slot.lock().unwrap_or_else(PoisonError::into_inner)
    }
}

#[cfg(test)]
mod tests {
    use std::sync::{Condvar, Mutex};
    use std::time::{Duration, Instant};

    use shottrainer_controller::DataPaths;

    use super::*;
    use crate::fake;
    use crate::wire::event::WireSessionState;

    const WAIT: Duration = Duration::from_secs(10);

    #[derive(Default)]
    struct Recorded {
        events: Vec<WireEvent>,
    }

    /// Keeps every event. No frame channel is subscribed.
    #[derive(Clone, Default)]
    struct RecordingOutlet {
        recorded: Arc<(Mutex<Recorded>, Condvar)>,
    }

    impl Outlet for RecordingOutlet {
        fn emit(&self, event: &WireEvent) {
            let (recorded, changed) = &*self.recorded;
            recorded.lock().unwrap().events.push(event.clone());
            changed.notify_all();
        }

        fn send_pixels(&self, _packet: Vec<u8>) -> bool {
            false
        }
    }

    impl RecordingOutlet {
        /// Waits until `done` holds, failing after [`WAIT`].
        fn wait_for(&self, what: &str, done: impl Fn(&Recorded) -> bool) {
            let (recorded, changed) = &*self.recorded;
            let deadline = Instant::now() + WAIT;
            let mut guard = recorded.lock().unwrap();
            while !done(&guard) {
                let left = deadline.saturating_duration_since(Instant::now());
                assert!(!left.is_zero(), "timed out waiting for {what}");
                guard = changed.wait_timeout(guard, left).unwrap().0;
            }
        }

        fn events(&self) -> Vec<WireEvent> {
            self.recorded.0.lock().unwrap().events.clone()
        }

        fn clear(&self) {
            self.recorded.0.lock().unwrap().events.clear();
        }
    }

    fn has_session(recorded: &Recorded, state: WireSessionState) -> bool {
        recorded
            .events
            .iter()
            .any(|e| matches!(e, WireEvent::Session { state: s, .. } if *s == state))
    }

    struct Rig {
        _dir: tempfile::TempDir,
        outlet: RecordingOutlet,
        bridge: Bridge<RecordingOutlet>,
    }

    fn rig_with(outlet: RecordingOutlet, paths: impl FnOnce(&std::path::Path) -> DataPaths) -> Rig {
        let dir = tempfile::tempdir().unwrap();
        let config = ShellConfig {
            controller: ControllerConfig {
                paths: paths(dir.path()),
                app_version: "test".into(),
            },
            backends: Arc::new(fake::backends),
            mode: DeviceMode::Fake,
        };
        Rig {
            _dir: dir,
            bridge: Bridge::new(outlet.clone(), config),
            outlet,
        }
    }

    fn rig(outlet: RecordingOutlet) -> Rig {
        rig_with(outlet, DataPaths::in_dir)
    }

    #[test]
    fn ready_sends_the_state_the_webview_missed() {
        let rig = rig(RecordingOutlet::default());
        rig.bridge.spawn().unwrap();
        rig.outlet.clear();
        rig.bridge.ready().unwrap();
        rig.outlet.wait_for("the session state", |r| {
            has_session(r, WireSessionState::Idle)
        });
        let events = rig.outlet.events();
        assert!(
            matches!(events[0], WireEvent::Preferences { .. }),
            "{events:?}"
        );
        assert!(
            matches!(events[1], WireEvent::ZeroOffset { .. }),
            "{events:?}"
        );
    }

    #[test]
    fn a_command_from_the_webview_reaches_the_controller() {
        let rig = rig(RecordingOutlet::default());
        rig.bridge.spawn().unwrap();
        let command: crate::wire::WireCommand = serde_json::from_str(
            r#"{"type": "startSession", "name": "Morning", "category": "practice"}"#,
        )
        .unwrap();
        rig.bridge.send(command.into()).unwrap();
        rig.outlet.wait_for("a recording session", |r| {
            r.events.iter().any(|e| {
                matches!(
                    e,
                    WireEvent::Session {
                        state: WireSessionState::Recording { .. },
                        ..
                    }
                )
            })
        });
    }

    #[test]
    fn a_database_that_cannot_open_is_reported_by_status_and_send() {
        let rig = rig_with(RecordingOutlet::default(), |dir| {
            std::fs::write(dir.join("not-a-dir"), b"").unwrap();
            DataPaths::in_dir(&dir.join("not-a-dir"))
        });
        let error = rig.bridge.spawn().unwrap_err();
        assert!(error.contains("sessions database"), "{error}");
        let status = rig.bridge.status();
        assert!(!status.running);
        assert_eq!(status.error.as_deref(), Some(error.as_str()));
        assert_eq!(rig.bridge.send(Command::Refresh), Err(error.clone()));
        assert_eq!(rig.bridge.ready(), Err(error));
    }

    #[test]
    fn shutdown_stops_the_controller() {
        let rig = rig(RecordingOutlet::default());
        rig.bridge.spawn().unwrap();
        assert!(rig.bridge.status().running);
        rig.bridge.shutdown();
        let status = rig.bridge.status();
        assert!(!status.running);
        assert_eq!(status.error, None);
        assert_eq!(rig.bridge.send(Command::Refresh), Err(STOPPED.to_owned()));
    }

    #[test]
    fn status_reports_fake_devices_and_refused_access() {
        let rig = rig(RecordingOutlet::default());
        rig.bridge.access_denied("camera");
        let status = rig.bridge.status();
        assert!(status.fake_devices);
        assert_eq!(status.denied, ["camera"]);
        assert_eq!(
            serde_json::to_value(&status).unwrap(),
            serde_json::json!({"running": false, "error": null, "fakeDevices": true, "denied": ["camera"]})
        );
    }
}
