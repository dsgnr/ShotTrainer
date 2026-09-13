//! Connects one controller to the webview. Controller events become
//! [`WireEvent`] values on an [`Outlet`], frame pixels go to the frame
//! channel, and commands are refused once the controller thread has ended.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard, PoisonError};

use serde::Serialize;
use shottrainer_controller::{
    Backends, Command, ControllerConfig, ControllerHandle, RuntimeOptions, UiEvent, UiSink,
};

use crate::mode::DeviceMode;
use crate::pixels::{FrameGate, rgba_packet, unix_millis};
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
    /// True until device access is settled and `start` is called, while
    /// the system prompts for the camera and microphone may be showing.
    pub awaiting_access: bool,
}

struct Shared<O> {
    outlet: O,
    gate: FrameGate,
}

impl<O: Outlet> Shared<O> {
    fn deliver(&self, event: UiEvent) {
        self.outlet.emit(&WireEvent::from(&event));
        if let UiEvent::Frame(view) = &event
            && self.gate.try_acquire()
        {
            let packet = rgba_packet(&view.frame, view.frame_id, view.timestamp, unix_millis());
            if !self.outlet.send_pixels(packet) {
                self.gate.release();
            }
        }
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
    /// Set by the first `start`, once device access is settled.
    started: AtomicBool,
    denied: Mutex<Vec<String>>,
}

impl<O: Outlet> Bridge<O> {
    pub fn new(outlet: O, config: ShellConfig) -> Self {
        Bridge {
            shared: Arc::new(Shared {
                outlet,
                gate: FrameGate::default(),
            }),
            config,
            slot: Mutex::new(Slot::Empty),
            started: AtomicBool::new(false),
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
        self.started.store(true, Ordering::SeqCst);
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

    /// Replaces the controller with a new one, which opens the devices only
    /// if `start` was already called.
    pub fn restart(&self) -> Result<(), String> {
        let mut slot = self.slot();
        if let Slot::Running(handle) = std::mem::replace(&mut *slot, Slot::Empty) {
            handle.shutdown();
        }
        *slot = self.new_controller();
        match &*slot {
            Slot::Running(handle) => {
                if self.started.load(Ordering::SeqCst) {
                    handle.start();
                }
                Ok(())
            }
            Slot::Failed(error) => Err(error.clone()),
            Slot::Empty => Err(STOPPED.to_owned()),
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
            awaiting_access: !self.started.load(Ordering::SeqCst),
        }
    }

    pub fn access_denied(&self, media: &str) {
        log::warn!("Access to the {media} was refused");
        self.denied
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(media.to_owned());
    }

    /// The webview subscribed a new frame channel, so packets sent to an
    /// older one will never be reported drawn.
    pub fn frames_subscribed(&self) {
        self.shared.gate.reset();
    }

    pub fn frame_drawn(&self) {
        self.shared.gate.release();
    }

    fn slot(&self) -> MutexGuard<'_, Slot> {
        self.slot.lock().unwrap_or_else(PoisonError::into_inner)
    }
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::AtomicUsize;
    use std::sync::{Condvar, Mutex};
    use std::time::{Duration, Instant};

    use shottrainer_controller::DataPaths;
    use shottrainer_controller::backends::{CameraBackend, CameraHandle};
    use shottrainer_tracking::capture::{ClockFn, EventSink};
    use shottrainer_tracking::detector::{DetectorSettings, TargetDetector};
    use shottrainer_tracking::frame::Frame;
    use shottrainer_tracking::models::Detection;

    use super::*;
    use crate::fake::{self, DarkSpotDetector, SyntheticCamera};
    use crate::pixels::{HEADER_LEN, MAX_FRAMES_IN_FLIGHT};
    use crate::wire::event::WireSessionState;

    const WAIT: Duration = Duration::from_secs(10);

    #[derive(Default)]
    struct Recorded {
        events: Vec<WireEvent>,
        packets: Vec<Vec<u8>>,
    }

    /// Keeps everything delivered. Pixels are accepted only while
    /// `accepting` is set, as if a frame channel were subscribed.
    #[derive(Clone, Default)]
    struct RecordingOutlet {
        recorded: Arc<(Mutex<Recorded>, Condvar)>,
        accepting: Arc<AtomicBool>,
    }

    impl Outlet for RecordingOutlet {
        fn emit(&self, event: &WireEvent) {
            let (recorded, changed) = &*self.recorded;
            recorded.lock().unwrap().events.push(event.clone());
            changed.notify_all();
        }

        fn send_pixels(&self, packet: Vec<u8>) -> bool {
            if !self.accepting.load(Ordering::SeqCst) {
                return false;
            }
            let (recorded, changed) = &*self.recorded;
            recorded.lock().unwrap().packets.push(packet);
            changed.notify_all();
            true
        }
    }

    impl RecordingOutlet {
        fn accepting(self) -> Self {
            self.accepting.store(true, Ordering::SeqCst);
            self
        }

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

        fn packets(&self) -> Vec<Vec<u8>> {
            self.recorded.0.lock().unwrap().packets.clone()
        }

        fn clear(&self) {
            let mut recorded = self.recorded.0.lock().unwrap();
            recorded.events.clear();
            recorded.packets.clear();
        }

        fn frame_events(&self) -> usize {
            frame_count(&self.recorded.0.lock().unwrap())
        }
    }

    fn frame_count(recorded: &Recorded) -> usize {
        recorded
            .events
            .iter()
            .filter(|e| matches!(e, WireEvent::Frame(_)))
            .count()
    }

    fn has_session(recorded: &Recorded, state: WireSessionState) -> bool {
        recorded
            .events
            .iter()
            .any(|e| matches!(e, WireEvent::Session { state: s, .. } if *s == state))
    }

    /// Opens the synthetic camera and counts how often it was opened.
    struct CountingCamera(Arc<AtomicUsize>);

    impl CameraBackend for CountingCamera {
        fn list_cameras(&mut self, running: Option<i32>) -> Vec<(i64, String)> {
            SyntheticCamera.list_cameras(running)
        }

        fn start(
            &mut self,
            index: i32,
            clock: ClockFn,
            on_event: EventSink,
        ) -> Box<dyn CameraHandle> {
            self.0.fetch_add(1, Ordering::SeqCst);
            SyntheticCamera.start(index, clock, on_event)
        }
    }

    /// Panics on the first frame while `armed` is set.
    struct PanickingDetector {
        armed: Arc<AtomicBool>,
        inner: DarkSpotDetector,
    }

    impl TargetDetector for PanickingDetector {
        fn detect(&mut self, frame: &Frame) -> Detection {
            assert!(!self.armed.load(Ordering::SeqCst), "detector failure");
            self.inner.detect(frame)
        }

        fn reset_lock(&mut self) {}

        fn settings(&self) -> &DetectorSettings {
            self.inner.settings()
        }

        fn set_settings(&mut self, settings: DetectorSettings) {
            self.inner.set_settings(settings);
        }
    }

    struct Rig {
        _dir: tempfile::TempDir,
        outlet: RecordingOutlet,
        bridge: Bridge<RecordingOutlet>,
        camera_starts: Arc<AtomicUsize>,
        armed: Arc<AtomicBool>,
    }

    fn rig_with(outlet: RecordingOutlet, paths: impl FnOnce(&std::path::Path) -> DataPaths) -> Rig {
        let dir = tempfile::tempdir().unwrap();
        let camera_starts = Arc::new(AtomicUsize::new(0));
        let armed = Arc::new(AtomicBool::new(false));
        let backends: BackendFactory = {
            let (camera_starts, armed) = (camera_starts.clone(), armed.clone());
            Arc::new(move || {
                let mut backends = fake::backends();
                backends.camera = Box::new(CountingCamera(camera_starts.clone()));
                backends.detector = Box::new(PanickingDetector {
                    armed: armed.clone(),
                    inner: DarkSpotDetector::default(),
                });
                backends
            })
        };
        let config = ShellConfig {
            controller: ControllerConfig {
                paths: paths(dir.path()),
                app_version: "test".into(),
            },
            backends,
            mode: DeviceMode::Fake,
        };
        Rig {
            _dir: dir,
            bridge: Bridge::new(outlet.clone(), config),
            outlet,
            camera_starts,
            armed,
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
    fn frames_arrive_as_an_event_and_an_rgba_packet() {
        let rig = rig(RecordingOutlet::default().accepting());
        rig.bridge.spawn().unwrap();
        rig.bridge.start();
        rig.outlet
            .wait_for("a pixel packet", |r| !r.packets.is_empty());
        let packet = &rig.outlet.packets()[0];
        let width = u32::from_le_bytes(packet[0..4].try_into().unwrap());
        let height = u32::from_le_bytes(packet[4..8].try_into().unwrap());
        let frame_id = i64::from_le_bytes(packet[8..16].try_into().unwrap());
        assert_eq!((width, height), (fake::WIDTH, fake::HEIGHT));
        assert_eq!(packet.len(), HEADER_LEN + (width * height * 4) as usize);
        let events = rig.outlet.events();
        let frame = events.iter().find_map(|e| match e {
            WireEvent::Frame(f) if f.frame_id == frame_id => Some(f),
            _ => None,
        });
        let frame = frame.expect("a frame event with the packet's id");
        assert_eq!(frame.status, "tracking");
        assert!(frame.aim.is_some());
    }

    /// One delivery as `(is_packet, frame_id)`.
    type Call = (bool, i64);

    /// Logs the order of deliveries.
    #[derive(Clone, Default)]
    struct OrderOutlet {
        log: Arc<(Mutex<Vec<Call>>, Condvar)>,
    }

    impl Outlet for OrderOutlet {
        fn emit(&self, event: &WireEvent) {
            if let WireEvent::Frame(f) = event {
                self.log.0.lock().unwrap().push((false, f.frame_id));
                self.log.1.notify_all();
            }
        }

        fn send_pixels(&self, packet: Vec<u8>) -> bool {
            let id = i64::from_le_bytes(packet[8..16].try_into().unwrap());
            self.log.0.lock().unwrap().push((true, id));
            self.log.1.notify_all();
            true
        }
    }

    #[test]
    fn a_frame_event_precedes_its_packet() {
        let dir = tempfile::tempdir().unwrap();
        let outlet = OrderOutlet::default();
        let bridge = Bridge::new(
            outlet.clone(),
            ShellConfig {
                controller: ControllerConfig {
                    paths: DataPaths::in_dir(dir.path()),
                    app_version: "test".into(),
                },
                backends: Arc::new(fake::backends),
                mode: DeviceMode::Fake,
            },
        );
        bridge.spawn().unwrap();
        bridge.start();
        let (log, changed) = &*outlet.log;
        let deadline = Instant::now() + WAIT;
        let mut guard = log.lock().unwrap();
        while !guard.iter().any(|(packet, _)| *packet) {
            let left = deadline.saturating_duration_since(Instant::now());
            assert!(!left.is_zero(), "timed out waiting for a packet");
            guard = changed.wait_timeout(guard, left).unwrap().0;
        }
        let packet_at = guard.iter().position(|(packet, _)| *packet).unwrap();
        let id = guard[packet_at].1;
        let event_at = guard.iter().position(|e| *e == (false, id));
        assert!(
            event_at.is_some_and(|at| at < packet_at),
            "log was {:?}",
            *guard
        );
    }

    #[test]
    fn pixels_wait_for_the_webview_to_draw() {
        let rig = rig(RecordingOutlet::default().accepting());
        rig.bridge.spawn().unwrap();
        rig.bridge.start();
        rig.outlet.wait_for("ten frames", |r| frame_count(r) >= 10);
        assert_eq!(rig.outlet.packets().len(), MAX_FRAMES_IN_FLIGHT);
        rig.bridge.frame_drawn();
        let seen = rig.outlet.frame_events();
        rig.outlet
            .wait_for("five more frames", |r| frame_count(r) >= seen + 5);
        assert_eq!(rig.outlet.packets().len(), MAX_FRAMES_IN_FLIGHT + 1);
    }

    #[test]
    fn a_new_subscription_reopens_a_full_gate() {
        let rig = rig(RecordingOutlet::default().accepting());
        rig.bridge.spawn().unwrap();
        rig.bridge.start();
        rig.outlet.wait_for("ten frames", |r| frame_count(r) >= 10);
        rig.bridge.frames_subscribed();
        rig.outlet.wait_for("two more packets", |r| {
            r.packets.len() == MAX_FRAMES_IN_FLIGHT * 2
        });
    }

    #[test]
    fn pixels_without_a_channel_hold_no_slot() {
        let rig = rig(RecordingOutlet::default());
        rig.bridge.spawn().unwrap();
        rig.bridge.start();
        rig.outlet.wait_for("ten frames", |r| frame_count(r) >= 10);
        assert!(rig.outlet.packets().is_empty());
        rig.outlet.accepting.store(true, Ordering::SeqCst);
        rig.outlet.wait_for("a packet", |r| !r.packets.is_empty());
    }

    #[test]
    fn a_failed_controller_refuses_commands_until_restarted() {
        let rig = rig(RecordingOutlet::default());
        rig.armed.store(true, Ordering::SeqCst);
        rig.bridge.spawn().unwrap();
        rig.bridge.start();
        rig.outlet.wait_for("the failure event", |r| {
            r.events.iter().any(
                |e| matches!(e, WireEvent::ControllerFailed { reason } if reason == "detector failure"),
            )
        });
        assert!(!rig.bridge.status().running);
        assert_eq!(rig.bridge.send(Command::Refresh), Err(STOPPED.to_owned()));
        rig.armed.store(false, Ordering::SeqCst);
        rig.bridge.restart().unwrap();
        assert!(rig.bridge.status().running);
        rig.outlet.clear();
        rig.bridge.ready().unwrap();
        rig.outlet.wait_for("the session state", |r| {
            has_session(r, WireSessionState::Idle)
        });
        rig.outlet
            .wait_for("a frame from the new controller", |r| frame_count(r) > 0);
        assert_eq!(rig.camera_starts.load(Ordering::SeqCst), 2);
    }

    #[test]
    fn a_restart_before_start_opens_no_device() {
        let rig = rig(RecordingOutlet::default());
        rig.bridge.spawn().unwrap();
        rig.bridge.restart().unwrap();
        rig.bridge.ready().unwrap();
        rig.outlet.wait_for("the session state", |r| {
            has_session(r, WireSessionState::Idle)
        });
        assert_eq!(rig.camera_starts.load(Ordering::SeqCst), 0);
        rig.bridge.start();
        rig.outlet.wait_for("a frame", |r| frame_count(r) > 0);
        assert_eq!(rig.camera_starts.load(Ordering::SeqCst), 1);
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
            serde_json::json!({"running": false, "error": null, "fakeDevices": true, "denied": ["camera"], "awaitingAccess": true})
        );
    }

    #[test]
    fn status_reports_access_awaited_until_start() {
        let rig = rig(RecordingOutlet::default());
        assert!(rig.bridge.status().awaiting_access);
        rig.bridge.start();
        assert!(!rig.bridge.status().awaiting_access);
    }
}
