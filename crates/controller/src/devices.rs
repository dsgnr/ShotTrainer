//! Port of `app/camera_manager.py` and the audio listener lifecycle the
//! Python controller drives. Device events are tagged with a generation so
//! late events from a stopped device are ignored.

use std::path::PathBuf;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

use shottrainer_audio::models::ShotDetectorSettings;
use shottrainer_audio::{AudioEvent, DeviceSelector};
use shottrainer_settings::stores::{
    CameraSelection, load_camera_selection, resolve_camera_index, save_camera_selection,
};
use shottrainer_tracking::capture::{CameraEvent, ClockFn};

use crate::backends::{AudioBackend, AudioHandle, CameraBackend, CameraHandle};

/// Frames waiting for the controller beyond this are dropped at the capture
/// thread, so a slow consumer cannot build an unbounded queue.
pub const MAX_PENDING_FRAMES: usize = 2;

#[derive(Debug, Clone, PartialEq)]
pub enum DeviceEvent {
    Camera { generation: u64, event: CameraEvent },
    Audio { generation: u64, event: AudioEvent },
}

/// Delivers device events to the controller's input queue.
pub type DeviceForward = Arc<dyn Fn(DeviceEvent) + Send + Sync + 'static>;

pub struct CameraManager {
    backend: Box<dyn CameraBackend>,
    forward: DeviceForward,
    clock: ClockFn,
    selection_path: PathBuf,
    running: Option<(i32, Box<dyn CameraHandle>)>,
    generation: u64,
    /// Frames in flight for the current capture. Each start gets its own
    /// counter so frames of an earlier capture cannot use up its budget.
    pending: Arc<AtomicUsize>,
    cameras: Option<Vec<(i64, String)>>,
}

impl CameraManager {
    pub fn new(
        backend: Box<dyn CameraBackend>,
        forward: DeviceForward,
        clock: ClockFn,
        selection_path: PathBuf,
    ) -> Self {
        CameraManager {
            backend,
            forward,
            clock,
            selection_path,
            running: None,
            generation: 0,
            pending: Arc::new(AtomicUsize::new(0)),
            cameras: None,
        }
    }

    /// The camera to open at start-up. A saved name wins over the saved
    /// index, which wins over the first camera. `None` only when the user
    /// chose no camera and nothing is attached.
    pub fn effective_index(&mut self) -> Option<i32> {
        let selection = load_camera_selection(&self.selection_path);
        if selection.index.is_none() && selection.name.is_empty() {
            return None;
        }
        let available = self.cameras(false);
        let index = if available.is_empty() {
            selection.index?
        } else {
            resolve_camera_index(&selection, &available)
        };
        i32::try_from(index)
            .inspect_err(|_| log::warn!("Camera index {index} is out of range"))
            .ok()
    }

    /// Stops any running camera and starts `index`.
    pub fn start(&mut self, index: i32) {
        self.stop();
        self.generation += 1;
        let generation = self.generation;
        let forward = self.forward.clone();
        let pending = Arc::new(AtomicUsize::new(0));
        self.pending = pending.clone();
        let sink = Box::new(move |event: CameraEvent| {
            if matches!(event, CameraEvent::Frame { .. })
                && pending.fetch_add(1, Ordering::AcqRel) >= MAX_PENDING_FRAMES
            {
                pending.fetch_sub(1, Ordering::AcqRel);
                log::debug!("Dropping a camera frame, the controller is behind");
                return;
            }
            forward(DeviceEvent::Camera { generation, event });
        });
        let handle = self.backend.start(index, self.clock.clone(), sink);
        self.running = Some((index, handle));
    }

    /// Stops the camera. Returns `true` when one was running.
    pub fn stop(&mut self) -> bool {
        match self.running.take() {
            Some((_, mut handle)) => {
                handle.stop();
                true
            }
            None => false,
        }
    }

    pub fn device_index(&self) -> Option<i32> {
        self.running.as_ref().map(|(index, _)| *index)
    }

    /// Events from an earlier capture are stale.
    pub fn is_current(&self, generation: u64) -> bool {
        self.running.is_some() && generation == self.generation
    }

    /// Called once for every frame event taken off the queue. Frames of an
    /// earlier generation are ignored, as they were counted against a
    /// counter that is no longer in use.
    pub fn frame_done(&self, generation: u64) {
        if generation != self.generation {
            return;
        }
        let mut current = self.pending.load(Ordering::Acquire);
        while current > 0 {
            match self.pending.compare_exchange_weak(
                current,
                current - 1,
                Ordering::AcqRel,
                Ordering::Acquire,
            ) {
                Ok(_) => break,
                Err(actual) => current = actual,
            }
        }
    }

    /// The enumerated cameras, cached until a forced refresh.
    pub fn cameras(&mut self, force_refresh: bool) -> Vec<(i64, String)> {
        if force_refresh || self.cameras.is_none() {
            self.cameras = Some(self.backend.list_cameras());
        }
        self.cameras.clone().unwrap_or_default()
    }

    /// The list for the Preferences dialog, never empty.
    pub fn device_options(&mut self, force_refresh: bool) -> Vec<(i64, String)> {
        let cameras = self.cameras(force_refresh);
        if cameras.is_empty() {
            vec![(0, "Camera 0".to_owned())]
        } else {
            cameras
        }
    }

    /// Saves the chosen camera by name, taken from the last enumeration.
    pub fn persist_selection(&self, index: Option<i32>) {
        let selection = match index {
            None => CameraSelection {
                name: String::new(),
                index: None,
            },
            Some(index) => {
                let index = i64::from(index);
                let name = self
                    .cameras
                    .iter()
                    .flatten()
                    .find(|(i, _)| *i == index)
                    .map_or_else(|| format!("Camera {index}"), |(_, name)| name.clone());
                CameraSelection {
                    name,
                    index: Some(index),
                }
            }
        };
        if let Err(error) = save_camera_selection(&selection, &self.selection_path) {
            log::warn!("Could not save camera selection: {error}");
        }
    }
}

pub struct AudioManager {
    backend: Box<dyn AudioBackend>,
    forward: DeviceForward,
    clock: ClockFn,
    settings: ShotDetectorSettings,
    device: String,
    running: Option<Box<dyn AudioHandle>>,
    /// Set when the current stream reported an error. `AudioInput` ends its
    /// stream thread after a failed open or play, so the handle is dead.
    failed: Arc<AtomicBool>,
    generation: u64,
}

impl AudioManager {
    pub fn new(backend: Box<dyn AudioBackend>, forward: DeviceForward, clock: ClockFn) -> Self {
        AudioManager {
            backend,
            forward,
            clock,
            settings: ShotDetectorSettings::default(),
            device: "default".to_owned(),
            running: None,
            failed: Arc::new(AtomicBool::new(false)),
            generation: 0,
        }
    }

    /// Applies at once to a running stream.
    pub fn update_settings(&mut self, settings: ShotDetectorSettings) {
        if let Some(handle) = &self.running {
            handle.update_settings(settings.clone());
        }
        self.settings = settings;
    }

    /// Takes effect at the next start, as in Python. A running stream stays
    /// on its device.
    pub fn set_device(&mut self, device: &str) {
        device.clone_into(&mut self.device);
    }

    /// Opens the stream unless one is running. Errors arrive as events, and
    /// a start after an error opens a new stream.
    pub fn start(&mut self) {
        if self.running.is_some() {
            if !self.failed.load(Ordering::Acquire) {
                return;
            }
            self.stop();
        }
        let failed = Arc::new(AtomicBool::new(false));
        self.failed = failed.clone();
        self.generation += 1;
        let generation = self.generation;
        let forward = self.forward.clone();
        let sink = Box::new(move |event| {
            if matches!(event, AudioEvent::Error(_)) {
                failed.store(true, Ordering::Release);
            }
            forward(DeviceEvent::Audio { generation, event });
        });
        self.running = Some(self.backend.start(
            self.settings.clone(),
            DeviceSelector::parse(Some(&self.device)),
            self.clock.clone(),
            sink,
        ));
    }

    pub fn stop(&mut self) {
        if let Some(mut handle) = self.running.take() {
            handle.stop();
        }
    }

    pub fn is_current(&self, generation: u64) -> bool {
        self.running.is_some() && generation == self.generation
    }

    pub fn list_inputs(&mut self) -> Vec<String> {
        self.backend.list_inputs()
    }
}
#[cfg(test)]
mod tests {
    use std::sync::Mutex;

    use shottrainer_tracking::frame::{Frame, PixelFormat};

    use super::*;
    use crate::fakes::{FakeAudio, FakeCamera};

    fn collector() -> (DeviceForward, Arc<Mutex<Vec<DeviceEvent>>>) {
        let seen = Arc::new(Mutex::new(Vec::new()));
        let sink = seen.clone();
        (
            Arc::new(move |event| sink.lock().unwrap().push(event)),
            seen,
        )
    }

    fn clock() -> ClockFn {
        Arc::new(|| 0.0)
    }

    fn frame_event(id: i64) -> CameraEvent {
        CameraEvent::Frame {
            frame: Frame::filled(2, 2, PixelFormat::Grey, 0).unwrap(),
            timestamp: 0.0,
            frame_id: id,
        }
    }

    fn manager(
        cameras: &[(i64, &str)],
    ) -> (
        CameraManager,
        FakeCamera,
        Arc<Mutex<Vec<DeviceEvent>>>,
        tempfile::TempDir,
    ) {
        let dir = tempfile::tempdir().unwrap();
        let fake = FakeCamera::with_cameras(cameras);
        let (forward, seen) = collector();
        let mgr = CameraManager::new(
            Box::new(fake.clone()),
            forward,
            clock(),
            dir.path().join("camera_selection.json"),
        );
        (mgr, fake, seen, dir)
    }

    fn save_selection(dir: &tempfile::TempDir, name: &str, index: Option<i64>) {
        let selection = CameraSelection {
            name: name.to_owned(),
            index,
        };
        save_camera_selection(&selection, &dir.path().join("camera_selection.json")).unwrap();
    }

    #[test]
    fn effective_index_prefers_the_saved_name() {
        let (mut mgr, _, _, dir) = manager(&[(0, "Built-in"), (2, "USB Cam")]);
        save_selection(&dir, "USB Cam", Some(0));
        assert_eq!(mgr.effective_index(), Some(2));
    }

    #[test]
    fn effective_index_respects_no_camera() {
        let (mut mgr, fake, _, dir) = manager(&[(0, "Built-in")]);
        save_selection(&dir, "", None);
        assert_eq!(mgr.effective_index(), None);
        assert_eq!(fake.state().lists, 0, "no enumeration for no camera");
    }

    #[test]
    fn effective_index_without_devices_uses_the_saved_index() {
        let (mut mgr, _, _, dir) = manager(&[]);
        assert_eq!(
            mgr.effective_index(),
            Some(0),
            "the default selection is index 0"
        );
        save_selection(&dir, "Gone", None);
        assert_eq!(mgr.effective_index(), None);
        save_selection(&dir, "Gone", Some(i64::MAX));
        assert_eq!(
            mgr.effective_index(),
            None,
            "an index beyond i32 is refused"
        );
    }

    #[test]
    fn enumeration_is_cached_until_refreshed() {
        let (mut mgr, fake, _, _dir) = manager(&[(0, "A")]);
        mgr.cameras(false);
        mgr.cameras(false);
        assert_eq!(fake.state().lists, 1);
        mgr.cameras(true);
        assert_eq!(fake.state().lists, 2);
    }

    #[test]
    fn device_options_are_never_empty() {
        let (mut mgr, _, _, _dir) = manager(&[]);
        assert_eq!(mgr.device_options(false), [(0, "Camera 0".to_owned())]);
    }

    #[test]
    fn start_replaces_the_running_camera_and_tags_its_events() {
        let (mut mgr, fake, seen, _dir) = manager(&[]);
        mgr.start(1);
        mgr.start(3);
        assert_eq!(fake.state().started, [1, 3]);
        assert_eq!(fake.state().stopped, 1);
        assert_eq!(mgr.device_index(), Some(3));
        fake.emit(0, CameraEvent::Closed);
        fake.emit(1, CameraEvent::Error("boom".into()));
        let seen = seen.lock().unwrap();
        assert_eq!(
            *seen,
            [
                DeviceEvent::Camera {
                    generation: 1,
                    event: CameraEvent::Closed
                },
                DeviceEvent::Camera {
                    generation: 2,
                    event: CameraEvent::Error("boom".into())
                },
            ]
        );
        assert!(!mgr.is_current(1));
        assert!(mgr.is_current(2));
    }

    #[test]
    fn stop_reports_whether_a_camera_was_running() {
        let (mut mgr, fake, _, _dir) = manager(&[]);
        assert!(!mgr.stop());
        mgr.start(0);
        assert!(mgr.stop());
        assert_eq!((mgr.device_index(), fake.state().stopped), (None, 1));
        assert!(!mgr.is_current(1), "nothing is current once stopped");
    }

    #[test]
    fn frames_beyond_the_pending_limit_are_dropped() {
        let (mut mgr, fake, seen, _dir) = manager(&[]);
        mgr.start(0);
        for id in 1..=4 {
            fake.emit(0, frame_event(id));
        }
        fake.emit(0, CameraEvent::Closed);
        assert_eq!(seen.lock().unwrap().len(), MAX_PENDING_FRAMES + 1);
        mgr.frame_done(1);
        fake.emit(0, frame_event(5));
        assert_eq!(seen.lock().unwrap().len(), MAX_PENDING_FRAMES + 2);
        for _ in 0..10 {
            mgr.frame_done(1);
        }
        fake.emit(0, frame_event(6));
        assert_eq!(
            seen.lock().unwrap().len(),
            MAX_PENDING_FRAMES + 3,
            "extra frame_done calls do not underflow"
        );
    }

    #[test]
    fn a_restarted_camera_has_its_own_frame_budget() {
        let (mut mgr, fake, seen, _dir) = manager(&[]);
        mgr.start(0);
        fake.emit(0, frame_event(1));
        fake.emit(0, frame_event(2));
        mgr.start(0);
        for id in 3..=5 {
            fake.emit(1, frame_event(id));
        }
        let frames = seen
            .lock()
            .unwrap()
            .iter()
            .filter(|e| matches!(e, DeviceEvent::Camera { generation: 2, .. }))
            .count();
        assert_eq!(frames, MAX_PENDING_FRAMES);
        mgr.frame_done(1);
        mgr.frame_done(1);
        fake.emit(1, frame_event(6));
        assert_eq!(
            seen.lock().unwrap().len(),
            2 + MAX_PENDING_FRAMES,
            "stale frame_done calls do not free the new budget"
        );
    }

    #[test]
    fn effective_index_falls_back_to_the_first_camera() {
        let (mut mgr, _, _, dir) = manager(&[(4, "Built-in"), (2, "USB Cam")]);
        save_selection(&dir, "Gone", Some(9));
        assert_eq!(mgr.effective_index(), Some(4));
    }

    #[test]
    fn audio_start_retries_after_a_failed_open() {
        let fake = FakeAudio::default();
        let (forward, _) = collector();
        let mut mgr = AudioManager::new(Box::new(fake.clone()), forward, clock());
        mgr.start();
        fake.emit(0, AudioEvent::Error("no device".into()));
        assert!(mgr.is_current(1), "the error itself is still current");
        mgr.start();
        assert_eq!(fake.state().started.len(), 2);
        assert_eq!(fake.state().stopped, 1, "the failed stream is released");
        assert!(mgr.is_current(2));
        assert!(!mgr.is_current(1));
    }

    #[test]
    fn audio_is_not_current_after_stop() {
        let fake = FakeAudio::default();
        let (forward, _) = collector();
        let mut mgr = AudioManager::new(Box::new(fake), forward, clock());
        mgr.start();
        assert!(mgr.is_current(1));
        mgr.stop();
        assert!(!mgr.is_current(1));
    }

    #[test]
    fn the_selection_is_saved_by_name() {
        let (mut mgr, _, _, dir) = manager(&[(0, "Built-in"), (2, "USB Cam")]);
        let path = dir.path().join("camera_selection.json");
        mgr.persist_selection(Some(2));
        assert_eq!(
            load_camera_selection(&path).name,
            "Camera 2",
            "nothing enumerated yet"
        );
        mgr.cameras(false);
        mgr.persist_selection(Some(2));
        assert_eq!(
            load_camera_selection(&path),
            CameraSelection {
                name: "USB Cam".into(),
                index: Some(2)
            }
        );
        mgr.persist_selection(None);
        assert_eq!(
            load_camera_selection(&path),
            CameraSelection {
                name: String::new(),
                index: None
            }
        );
    }

    #[test]
    fn audio_starts_once_and_takes_a_new_device_at_the_next_start() {
        let fake = FakeAudio::default();
        let (forward, seen) = collector();
        let mut mgr = AudioManager::new(Box::new(fake.clone()), forward, clock());
        mgr.set_device("USB");
        mgr.start();
        mgr.start();
        mgr.set_device("2");
        assert_eq!(fake.state().started, [DeviceSelector::Name("USB".into())]);
        fake.emit(0, AudioEvent::Level(0.5));
        assert_eq!(
            *seen.lock().unwrap(),
            [DeviceEvent::Audio {
                generation: 1,
                event: AudioEvent::Level(0.5)
            }]
        );
        mgr.stop();
        mgr.start();
        assert_eq!(fake.state().started[1], DeviceSelector::Index(2));
        assert_eq!(fake.state().stopped, 1);
    }

    #[test]
    fn audio_settings_reach_a_running_stream() {
        let fake = FakeAudio::default();
        let (forward, _) = collector();
        let mut mgr = AudioManager::new(Box::new(fake.clone()), forward, clock());
        let settings = ShotDetectorSettings {
            threshold: 0.1,
            ..ShotDetectorSettings::default()
        };
        mgr.update_settings(settings.clone());
        mgr.start();
        assert_eq!(fake.state().start_settings, [settings]);
        let louder = ShotDetectorSettings {
            threshold: 0.9,
            ..ShotDetectorSettings::default()
        };
        mgr.update_settings(louder.clone());
        assert_eq!(fake.state().updates, [louder]);
    }
}
