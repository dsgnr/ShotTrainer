//! Port of `app/controller.py`. The controller owns every service and reacts
//! to one [`Input`] at a time on a single thread. It has no interface code,
//! takes [`Command`] values in and reports through [`UiEvent`] values.

use std::path::PathBuf;

use shottrainer_audio::AudioEvent;
use shottrainer_core::sessions::{DEFAULT_SESSION_CATEGORY, Db, SESSION_CATEGORIES, make_engine};
use shottrainer_settings::stores::{
    ZeroOffset, load_camera_selection, load_detector_settings, load_zero_offset, save_zero_offset,
};
use shottrainer_settings::target_faces::{
    TargetFace, built_in_faces, face_for_name, load_custom_faces, merged_faces, rings_for_face,
};
use shottrainer_settings::{Preferences, load_preferences, save_preferences, validate_preferences};
use shottrainer_tracking::capture::{CameraEvent, ClockFn};
use shottrainer_tracking::detector::TargetDetector;
use shottrainer_tracking::frame::Frame;

use crate::backends::Backends;
use crate::convert::{
    detector_from_store, effective_gain, frame_transform, shot_detector_settings,
};
use crate::devices::{AudioManager, CameraManager, DeviceEvent, DeviceForward};
use crate::events::{StatusMessage, UiEvent, UiSink};
use crate::frames::FramePipeline;
use crate::paths::DataPaths;
use crate::session::{SessionContext, SessionManager};
use crate::watcher::SettingsWatcher;

/// What the front end asks for. Destructive commands arrive after the front
/// end has asked the user to confirm.
#[derive(Debug, Clone, PartialEq)]
pub enum Command {
    StartSession {
        name: String,
        category: String,
    },
    StopSession,
    ClearShots,
    DeleteShot(usize),
    Rescore,
    SelectShot(usize),
    ListSessions,
    OpenSession(i64),
    RenameSession {
        id: i64,
        name: String,
    },
    SetSessionCategory {
        id: i64,
        category: String,
    },
    DeleteSession(i64),
    ExportSession {
        id: i64,
        dir: PathBuf,
    },
    ReplayPlay,
    ReplayPause,
    ReplayReset,
    ReplaySeek(f64),
    /// The Preferences dialog was saved.
    SetPreferences(Preferences),
    SetCircleDiameter(f64),
    ZeroOnAim,
    ClearZero,
    /// `refresh` enumerates the cameras again.
    ListDevices {
        refresh: bool,
    },
    ListTargetFaces,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Input {
    Command(Command),
    Device(DeviceEvent),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ControllerConfig {
    pub paths: DataPaths,
    /// Stored with each new session.
    pub app_version: String,
}

#[derive(Debug, thiserror::Error)]
pub enum ControllerError {
    #[error("the sessions database path is not valid UTF-8: {0}")]
    DatabasePath(PathBuf),
    #[error("could not open the sessions database: {0}")]
    Database(#[from] shottrainer_core::sessions::DatabaseError),
}

pub struct Controller {
    pub(crate) paths: DataPaths,
    pub(crate) app_version: String,
    pub(crate) sink: UiSink,
    pub(crate) clock: ClockFn,
    pub(crate) db: Db,
    pub(crate) faces: Vec<TargetFace>,
    pub(crate) prefs: Preferences,
    pub(crate) session: SessionManager,
    pub(crate) frames: FramePipeline,
    pub(crate) camera: CameraManager,
    pub(crate) audio: AudioManager,
    pub(crate) watcher: SettingsWatcher,
}

impl Controller {
    /// Opens the database and loads every settings file. Device events from
    /// the backends are delivered through `forward`, which must queue them
    /// for [`Controller::handle`] on the controller's thread. Nothing is
    /// started until [`Controller::start`], so the caller can first ask the
    /// operating system for camera and microphone access.
    pub fn new(
        config: ControllerConfig,
        backends: Backends,
        clock: ClockFn,
        forward: DeviceForward,
        sink: UiSink,
    ) -> Result<Self, ControllerError> {
        let ControllerConfig { paths, app_version } = config;
        let db_path = paths
            .sessions_db
            .to_str()
            .ok_or_else(|| ControllerError::DatabasePath(paths.sessions_db.clone()))?;
        let db = make_engine(db_path)?;
        let faces = merged_faces(
            &built_in_faces(),
            &load_custom_faces(&paths.custom_target_faces),
        );
        let prefs = load_preferences(&paths.settings);
        let mut controller = Controller {
            session: SessionManager::new(&prefs),
            frames: FramePipeline::new(&prefs, backends.detector),
            camera: CameraManager::new(
                backends.camera,
                forward.clone(),
                clock.clone(),
                paths.camera_selection.clone(),
            ),
            audio: AudioManager::new(backends.audio, forward, clock.clone()),
            watcher: SettingsWatcher::new(paths.settings.clone()),
            paths,
            app_version,
            sink,
            clock,
            db,
            faces,
            prefs,
        };
        controller.push_preferences();
        // Saved detector tuning wins over the region fraction from the
        // preferences, as in Python.
        if let Some(saved) = load_detector_settings(&controller.paths.detector_settings) {
            controller
                .frames
                .tracker_mut()
                .detector_mut()
                .set_settings(detector_from_store(&saved));
        }
        controller.watcher.start();
        let offset = load_zero_offset(&controller.paths.zero_offset)
            .map_or((0.0, 0.0), |z| (z.x_mm, z.y_mm));
        let active = offset != (0.0, 0.0);
        if active {
            controller
                .frames
                .tracker_mut()
                .set_zero_offset(offset.0, offset.1);
        }
        controller.emit(UiEvent::ZeroOffset {
            active,
            offset_mm: offset,
        });
        Ok(controller)
    }

    /// Starts the saved camera and the microphone. Both open on their own
    /// threads, so a permission prompt does not block the controller.
    pub fn start(&mut self) {
        if let Some(index) = self.camera.effective_index() {
            self.camera.start(index);
        }
        self.audio.start();
    }

    /// Saves a running recording and stops the devices.
    pub fn shutdown(&mut self) {
        if self.session.is_recording() {
            self.with_session(|session, cx| session.stop(cx));
        }
        self.camera.stop();
        self.audio.stop();
    }

    pub fn preferences(&self) -> &Preferences {
        &self.prefs
    }

    pub fn session(&self) -> &SessionManager {
        &self.session
    }

    pub fn frames(&self) -> &FramePipeline {
        &self.frames
    }

    /// When the replay player next needs [`Controller::tick`], in seconds on
    /// the controller clock.
    pub fn next_deadline(&self) -> Option<f64> {
        self.session.player().deadline()
    }

    /// Advances the replay player if its deadline has passed.
    pub fn tick(&mut self) {
        let now = (self.clock)();
        self.with_session(|session, cx| session.replay_tick(cx, now));
    }

    /// Applies `settings.json` when another program has changed it.
    pub fn poll_settings(&mut self) {
        if let Some(prefs) = self.watcher.poll() {
            self.on_settings_file_changed(prefs);
        }
    }

    pub fn handle(&mut self, input: Input) {
        match input {
            Input::Command(command) => self.handle_command(command),
            Input::Device(DeviceEvent::Camera { generation, event }) => {
                self.on_camera_event(generation, event);
            }
            Input::Device(DeviceEvent::Audio { generation, event }) => {
                self.on_audio_event(generation, event);
            }
        }
    }

    fn handle_command(&mut self, command: Command) {
        let now = (self.clock)();
        match command {
            Command::StartSession { name, category } => {
                let category = if SESSION_CATEGORIES.contains(&category.as_str()) {
                    category
                } else {
                    log::warn!("Unknown session category {category:?}, using the default");
                    DEFAULT_SESSION_CATEGORY.to_owned()
                };
                let version = self.app_version.clone();
                self.with_session(|s, cx| s.start(cx, &name, &category, &version));
            }
            Command::StopSession => self.with_session(|s, cx| s.stop(cx)),
            Command::ClearShots => self.with_session(|s, cx| s.clear_shots(cx)),
            Command::DeleteShot(index) => self.with_session(|s, cx| s.delete_shot(cx, index)),
            Command::Rescore => self.with_session(|s, cx| s.rescore(cx)),
            Command::SelectShot(index) => self.with_session(|s, cx| s.select_shot(cx, index)),
            Command::ListSessions => self.with_session(|s, cx| s.list_sessions(cx)),
            Command::OpenSession(id) => {
                let outcome = self.with_session(|s, cx| s.open_session(cx, id));
                if let Some(face) = outcome.switch_face {
                    self.set_target_face(&face);
                }
            }
            Command::RenameSession { id, name } => {
                self.with_session(|s, cx| s.rename_session(cx, id, &name));
            }
            Command::SetSessionCategory { id, category } => {
                self.with_session(|s, cx| s.set_session_category(cx, id, &category));
            }
            Command::DeleteSession(id) => self.with_session(|s, cx| s.delete_session(cx, id)),
            Command::ExportSession { id, dir } => {
                self.with_session(|s, cx| s.export_session(cx, id, &dir));
            }
            Command::ReplayPlay => self.with_session(|s, cx| s.replay_play(cx, now)),
            Command::ReplayPause => self.with_session(|s, cx| s.replay_pause(cx)),
            Command::ReplayReset => self.with_session(|s, cx| s.replay_reset(cx)),
            Command::ReplaySeek(fraction) => {
                self.with_session(|s, cx| s.replay_seek(cx, fraction, now));
            }
            Command::SetPreferences(prefs) => {
                self.apply_preferences(validate_preferences(&prefs), true);
            }
            Command::SetCircleDiameter(diameter_mm) => self.on_circle_diameter(diameter_mm),
            Command::ZeroOnAim => self.zero_on_aim(),
            Command::ClearZero => self.clear_zero(),
            Command::ListDevices { refresh } => {
                let cameras = self.camera.device_options(refresh);
                let microphones = self.audio.list_inputs();
                let saved_camera = load_camera_selection(&self.paths.camera_selection).name;
                self.emit(UiEvent::DeviceOptions {
                    cameras,
                    microphones,
                    saved_camera,
                });
            }
            Command::ListTargetFaces => self.emit(UiEvent::TargetFaces(self.faces.clone())),
        }
    }

    fn on_camera_event(&mut self, generation: u64, event: CameraEvent) {
        if matches!(event, CameraEvent::Frame { .. }) {
            self.camera.frame_done(generation);
        }
        if !self.camera.is_current(generation) {
            return;
        }
        match event {
            CameraEvent::Frame {
                frame,
                timestamp,
                frame_id,
            } => self.on_frame(frame, timestamp, frame_id),
            CameraEvent::Error(text) => {
                self.message(StatusMessage::warning(format!("Camera: {text}"), 5000));
            }
            CameraEvent::Opened { width, height, fps } => {
                log::info!("Camera opened at {width}x{height}, {fps} fps");
            }
            CameraEvent::Closed => log::info!("Camera closed"),
        }
    }

    fn on_frame(&mut self, frame: Frame, timestamp: f64, frame_id: i64) {
        let reviewing = self.session.reviewing().is_some();
        let Some(outcome) = self.frames.process(frame, timestamp, frame_id, reviewing) else {
            return;
        };
        if let Some(sample) = outcome.sample {
            self.with_session(|s, cx| s.on_sample(cx, sample));
        }
        self.emit(UiEvent::Frame(Box::new(outcome.view)));
        if let Some(text) = outcome.status_text {
            self.emit(UiEvent::TrackingStatusText(text));
        }
    }

    fn on_audio_event(&mut self, generation: u64, event: AudioEvent) {
        if !self.audio.is_current(generation) {
            return;
        }
        match event {
            AudioEvent::Level(level) => {
                self.emit(UiEvent::AudioLevel(level * effective_gain(&self.prefs)));
            }
            AudioEvent::Shot(shot) => self.with_session(|s, cx| s.on_shot(cx, shot)),
            AudioEvent::Error(text) => {
                self.message(StatusMessage::warning(format!("Audio: {text}"), 5000));
            }
            AudioEvent::Started => log::info!("Microphone started"),
            AudioEvent::Stopped => log::info!("Microphone stopped"),
        }
    }

    /// Python `_apply_preferences`, the one place that reacts to changed
    /// preferences, whether from the interface or from the file.
    pub(crate) fn apply_preferences(&mut self, prefs: Preferences, persist: bool) {
        let previous = std::mem::replace(&mut self.prefs, prefs);
        self.push_preferences();
        if previous.camera_id != self.prefs.camera_id {
            match self.prefs.camera_id {
                None => self.stop_camera(),
                Some(index) => self.camera.start(index),
            }
            self.camera.persist_selection(self.prefs.camera_id);
        }
        if persist && previous != self.prefs {
            if let Err(error) = save_preferences(&self.prefs, &self.paths.settings) {
                log::warn!("Could not save preferences: {error}");
            }
            self.watcher.mark_seen();
        }
    }

    /// Pushes the current preferences into every service and the interface.
    fn push_preferences(&mut self) {
        let prefs = &self.prefs;
        self.session.update_settings(prefs);
        self.audio.update_settings(shot_detector_settings(prefs));
        self.audio.set_device(&prefs.audio_device);
        self.frames.set_transform(frame_transform(prefs));
        let tracker = self.frames.tracker_mut();
        if let Err(error) = tracker.set_circle_diameter_mm(prefs.circle_diameter_mm) {
            log::warn!("Keeping the circle diameter: {error}");
        }
        tracker.set_region_fraction(prefs.tracking_region_fraction);
        tracker.set_trace_inversion(prefs.invert_trace_horizontal, prefs.invert_trace_vertical);
        let rings = rings_for_face(&self.faces, &prefs.target_face).to_vec();
        self.emit(UiEvent::Preferences {
            prefs: self.prefs.clone(),
            rings,
        });
    }

    fn on_settings_file_changed(&mut self, prefs: Preferences) {
        if prefs == self.prefs {
            return;
        }
        self.apply_preferences(prefs, false);
        self.message(StatusMessage::info("Preferences updated from disk", 3000));
    }

    fn on_circle_diameter(&mut self, diameter_mm: f64) {
        if (diameter_mm - self.prefs.circle_diameter_mm).abs() <= 1e-6 {
            return;
        }
        let prefs = Preferences {
            circle_diameter_mm: diameter_mm,
            ..self.prefs.clone()
        };
        self.apply_preferences(validate_preferences(&prefs), true);
    }

    /// Switches to a saved session's face when the catalogue has it.
    fn set_target_face(&mut self, key: &str) {
        if face_for_name(&self.faces, key).is_none() {
            log::warn!("Session references unknown face {key:?}, keeping current");
            return;
        }
        let prefs = Preferences {
            target_face: key.to_owned(),
            ..self.prefs.clone()
        };
        self.apply_preferences(prefs, true);
    }

    fn zero_on_aim(&mut self) {
        let tracker = self.frames.tracker_mut();
        if !tracker.zero_at_last_sample() {
            self.message(StatusMessage::info(
                "Aim at the target until the trace is live, then try again",
                4000,
            ));
            return;
        }
        let offset = tracker.zero_offset_mm();
        self.persist_zero_offset(offset);
        self.emit(UiEvent::ZeroOffset {
            active: true,
            offset_mm: offset,
        });
        self.emit(UiEvent::ClearLiveTrace);
        self.message(StatusMessage::info(
            format!("Trace zeroed: offset ({:.1}, {:.1}) mm", offset.0, offset.1),
            4000,
        ));
    }

    fn clear_zero(&mut self) {
        self.frames.tracker_mut().clear_zero_offset();
        self.persist_zero_offset((0.0, 0.0));
        self.emit(UiEvent::ZeroOffset {
            active: false,
            offset_mm: (0.0, 0.0),
        });
        self.emit(UiEvent::ClearLiveTrace);
        self.message(StatusMessage::info("Zero offset cleared", 2000));
    }

    /// An offset of zero removes the file.
    fn persist_zero_offset(&self, (x_mm, y_mm): (f64, f64)) {
        if let Err(error) = save_zero_offset(&ZeroOffset { x_mm, y_mm }, &self.paths.zero_offset) {
            log::warn!("Could not save zero offset: {error}");
        }
    }

    pub(crate) fn stop_camera(&mut self) {
        if self.camera.stop() {
            self.emit(UiEvent::CameraIdle);
        }
    }

    pub(crate) fn emit(&self, event: UiEvent) {
        (self.sink)(event);
    }

    pub(crate) fn message(&self, message: StatusMessage) {
        self.emit(UiEvent::Message(message));
    }

    pub(crate) fn with_session<T>(
        &mut self,
        f: impl FnOnce(&mut SessionManager, &SessionContext) -> T,
    ) -> T {
        let sink = &self.sink;
        let emit = |event| sink(event);
        let cx = SessionContext {
            db: &self.db,
            prefs: &self.prefs,
            faces: &self.faces,
            emit: &emit,
        };
        f(&mut self.session, &cx)
    }
}
#[cfg(test)]
mod tests {
    use shottrainer_audio::models::ShotEvent;
    use shottrainer_settings::stores::{
        CameraSelection, DetectorSettings as StoredDetectorSettings, save_camera_selection,
        save_detector_settings,
    };
    use shottrainer_tracking::frame::PixelFormat;

    use super::*;
    use crate::fakes::{TestRig, circle_at};
    use crate::frames::TrackingStatus;
    use crate::session::SessionState;

    fn frame_event(frame_id: i64, timestamp: f64) -> CameraEvent {
        CameraEvent::Frame {
            frame: Frame::filled(640, 480, PixelFormat::Grey, 0).unwrap(),
            timestamp,
            frame_id,
        }
    }

    fn command(controller: &mut Controller, command: Command) {
        controller.handle(Input::Command(command));
    }

    fn save_prefs(rig: &TestRig, prefs: &Preferences) {
        save_preferences(prefs, &rig.paths.settings).unwrap();
    }

    #[test]
    fn saved_preferences_reach_the_services_at_start_up() {
        let rig = TestRig::new();
        let prefs = Preferences {
            circle_diameter_mm: 85.0,
            camera_rotation: 90,
            audio_gain: 2.0,
            shot_threshold: 0.5,
            target_face: "air_rifle_10m".into(),
            ..Preferences::default()
        };
        save_prefs(&rig, &prefs);
        let controller = rig.build();
        assert_eq!(controller.preferences(), &prefs);
        assert_eq!(controller.frames().tracker().circle_diameter_mm(), 85.0);
        assert_eq!(controller.frames().transform().rotation_degrees, 90);
        let events = rig.take();
        let UiEvent::Preferences {
            prefs: shown,
            rings,
        } = &events[0]
        else {
            panic!("expected the preferences first, got {:?}", events[0]);
        };
        assert_eq!(shown, &prefs);
        assert!(!rings.is_empty());
        assert_eq!(
            events[1],
            UiEvent::ZeroOffset {
                active: false,
                offset_mm: (0.0, 0.0)
            }
        );
    }

    #[test]
    fn saved_detector_tuning_wins_over_the_region_preference() {
        let rig = TestRig::new();
        save_prefs(
            &rig,
            &Preferences {
                tracking_region_fraction: 0.9,
                ..Preferences::default()
            },
        );
        let stored = StoredDetectorSettings {
            region_fraction: 0.5,
            blur_kernel: 7,
            ..StoredDetectorSettings::default()
        };
        save_detector_settings(&stored, &rig.paths.detector_settings).unwrap();
        let controller = rig.build();
        let settings = controller.frames().tracker().detector().settings();
        assert_eq!((settings.region_fraction, settings.blur_kernel), (0.5, 7));
    }

    #[test]
    fn a_saved_zero_offset_is_applied() {
        let rig = TestRig::new();
        save_zero_offset(
            &ZeroOffset {
                x_mm: 1.5,
                y_mm: -2.0,
            },
            &rig.paths.zero_offset,
        )
        .unwrap();
        let controller = rig.build();
        assert_eq!(controller.frames().tracker().zero_offset_mm(), (1.5, -2.0));
        assert!(rig.take().contains(&UiEvent::ZeroOffset {
            active: true,
            offset_mm: (1.5, -2.0)
        }));
    }

    #[test]
    fn start_opens_the_saved_camera_and_the_microphone() {
        let rig = TestRig::new();
        rig.camera.state().cameras = vec![(0, "Built-in".into()), (3, "USB".into())];
        save_camera_selection(
            &CameraSelection {
                name: "USB".into(),
                index: Some(0),
            },
            &rig.paths.camera_selection,
        )
        .unwrap();
        save_prefs(
            &rig,
            &Preferences {
                audio_device: "Mic".into(),
                ..Preferences::default()
            },
        );
        let mut controller = rig.build();
        assert!(
            rig.camera.state().started.is_empty(),
            "nothing opens before start"
        );
        controller.start();
        assert_eq!(rig.camera.state().started, [3]);
        assert_eq!(
            rig.audio.state().started,
            [shottrainer_audio::DeviceSelector::Name("Mic".into())]
        );
    }

    #[test]
    fn no_saved_camera_opens_only_the_microphone() {
        let rig = TestRig::new();
        save_camera_selection(
            &CameraSelection {
                name: String::new(),
                index: None,
            },
            &rig.paths.camera_selection,
        )
        .unwrap();
        let mut controller = rig.build();
        controller.start();
        assert!(rig.camera.state().started.is_empty());
        assert_eq!(rig.audio.state().started.len(), 1);
    }

    #[test]
    fn camera_frames_are_tracked_and_shown() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        rig.take();
        rig.detector.push(circle_at(330.0, 240.0));
        rig.camera.emit(0, frame_event(5, 1.0));
        rig.pump(&mut controller);
        let events = rig.take();
        let UiEvent::Frame(view) = &events[0] else {
            panic!("expected a frame, got {events:?}");
        };
        assert_eq!(view.status, TrackingStatus::Tracking);
        assert_eq!(
            events[1],
            UiEvent::TrackingStatusText("Tracking 60 mm circle - 1.000 mm/px".into())
        );
        rig.audio.emit(
            0,
            AudioEvent::Shot(ShotEvent {
                timestamp: 1.0,
                audio_level: 0.5,
                sample_rate: 44100,
            }),
        );
        rig.pump(&mut controller);
        let shot = &controller.session().shots()[0];
        assert_eq!((shot.x_mm, shot.score.as_deref()), (Some(-10.0), Some("9")));
    }

    #[test]
    fn events_from_a_replaced_camera_are_ignored() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        command(
            &mut controller,
            Command::SetPreferences(Preferences {
                camera_id: Some(4),
                ..Preferences::default()
            }),
        );
        rig.take();
        rig.camera.emit(0, CameraEvent::Error("old".into()));
        rig.camera.emit(0, frame_event(1, 0.0));
        rig.camera.emit(1, CameraEvent::Error("new".into()));
        rig.pump(&mut controller);
        assert_eq!(rig.messages(), ["Camera: new"]);
        assert!(rig.detector.seen.lock().unwrap().is_empty());
    }

    #[test]
    fn audio_levels_are_scaled_by_the_gain_and_errors_shown() {
        let rig = TestRig::new();
        save_prefs(
            &rig,
            &Preferences {
                audio_gain: 4.0,
                ..Preferences::default()
            },
        );
        let mut controller = rig.build();
        controller.start();
        rig.take();
        rig.audio.emit(0, AudioEvent::Level(0.125));
        rig.audio.emit(0, AudioEvent::Error("denied".into()));
        rig.pump(&mut controller);
        let events = rig.take();
        assert_eq!(events[0], UiEvent::AudioLevel(0.5));
        assert_eq!(
            events[1],
            UiEvent::Message(StatusMessage::warning("Audio: denied", 5000))
        );
        assert_eq!(rig.audio.state().start_settings[0].threshold, 0.25 / 4.0);
    }

    #[test]
    fn set_preferences_saves_once_and_does_not_trigger_the_watcher() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        let prefs = Preferences {
            pre_shot_ms: 2000,
            ..Preferences::default()
        };
        command(&mut controller, Command::SetPreferences(prefs.clone()));
        assert_eq!(load_preferences(&rig.paths.settings), prefs);
        controller.poll_settings();
        assert!(
            !rig.messages()
                .contains(&"Preferences updated from disk".to_owned()),
            "our own save is not an external change"
        );
    }

    #[test]
    fn unchanged_preferences_are_not_saved() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        command(
            &mut controller,
            Command::SetPreferences(Preferences::default()),
        );
        assert!(!rig.paths.settings.exists());
    }

    #[test]
    fn invalid_preferences_from_the_interface_fall_back_per_value() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        let prefs = Preferences {
            camera_rotation: 45,
            circle_diameter_mm: f64::NAN,
            pre_shot_ms: 2000,
            ..Preferences::default()
        };
        command(&mut controller, Command::SetPreferences(prefs));
        let applied = controller.preferences();
        assert_eq!(
            (
                applied.camera_rotation,
                applied.circle_diameter_mm,
                applied.pre_shot_ms
            ),
            (0, 60.0, 2000)
        );
    }

    #[test]
    fn a_camera_change_restarts_the_camera_and_saves_the_selection() {
        let rig = TestRig::new();
        rig.camera.state().cameras = vec![(0, "Built-in".into()), (2, "USB".into())];
        let mut controller = rig.build();
        controller.start();
        command(&mut controller, Command::ListDevices { refresh: false });
        rig.take();
        let with_camera = |id| Preferences {
            camera_id: id,
            ..Preferences::default()
        };
        command(
            &mut controller,
            Command::SetPreferences(with_camera(Some(2))),
        );
        assert_eq!(rig.camera.state().started, [0, 2]);
        assert_eq!(
            load_camera_selection(&rig.paths.camera_selection),
            CameraSelection {
                name: "USB".into(),
                index: Some(2)
            }
        );
        command(&mut controller, Command::SetPreferences(with_camera(None)));
        assert!(rig.take().contains(&UiEvent::CameraIdle));
        assert_eq!(rig.camera.state().stopped, 2);
        assert_eq!(
            load_camera_selection(&rig.paths.camera_selection).index,
            None
        );
    }

    #[test]
    fn an_external_settings_edit_is_applied_without_saving_back() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        let text = r#"{"circle_diameter_mm": 99.0}"#;
        std::fs::write(&rig.paths.settings, text).unwrap();
        let file = std::fs::File::options()
            .write(true)
            .open(&rig.paths.settings)
            .unwrap();
        file.set_modified(std::time::SystemTime::UNIX_EPOCH + std::time::Duration::from_secs(9))
            .unwrap();
        rig.take();
        controller.poll_settings();
        assert_eq!(controller.frames().tracker().circle_diameter_mm(), 99.0);
        assert_eq!(std::fs::read_to_string(&rig.paths.settings).unwrap(), text);
        assert_eq!(rig.messages(), ["Preferences updated from disk"]);
        controller.poll_settings();
        assert!(rig.take().is_empty());
    }

    #[test]
    fn the_circle_diameter_ignores_rounding_noise() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        command(&mut controller, Command::SetCircleDiameter(60.0 + 1e-7));
        assert!(!rig.paths.settings.exists());
        command(&mut controller, Command::SetCircleDiameter(42.0));
        assert_eq!(controller.frames().tracker().circle_diameter_mm(), 42.0);
        assert_eq!(
            load_preferences(&rig.paths.settings).circle_diameter_mm,
            42.0
        );
    }

    #[test]
    fn zero_on_aim_needs_a_live_sample() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        rig.take();
        command(&mut controller, Command::ZeroOnAim);
        assert_eq!(
            rig.messages(),
            ["Aim at the target until the trace is live, then try again"]
        );
        assert!(!rig.paths.zero_offset.exists());
    }

    #[test]
    fn zero_on_aim_persists_the_offset_and_clear_removes_it() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        rig.detector.push(circle_at(330.0, 240.0));
        rig.camera.emit(0, frame_event(1, 0.0));
        rig.pump(&mut controller);
        rig.take();
        command(&mut controller, Command::ZeroOnAim);
        assert_eq!(controller.frames().tracker().zero_offset_mm(), (-10.0, 0.0));
        assert_eq!(
            load_zero_offset(&rig.paths.zero_offset),
            Some(ZeroOffset {
                x_mm: -10.0,
                y_mm: 0.0
            })
        );
        let events = rig.take();
        assert_eq!(
            events[..2],
            [
                UiEvent::ZeroOffset {
                    active: true,
                    offset_mm: (-10.0, 0.0)
                },
                UiEvent::ClearLiveTrace
            ]
        );
        assert_eq!(
            events[2],
            UiEvent::Message(StatusMessage::info(
                "Trace zeroed: offset (-10.0, 0.0) mm",
                4000
            ))
        );
        command(&mut controller, Command::ClearZero);
        assert!(!rig.paths.zero_offset.exists());
        assert_eq!(controller.frames().tracker().zero_offset_mm(), (0.0, 0.0));
    }

    #[test]
    fn opening_a_session_switches_to_its_face_when_known() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        let repo = shottrainer_core::sessions::SessionRepository::new(&controller.db);
        let new = |face| shottrainer_core::sessions::NewSession {
            target_profile: face,
            ..Default::default()
        };
        let known = repo.create_session(&new("air_rifle_10m")).unwrap();
        let unknown = repo.create_session(&new("no_such_face")).unwrap();
        command(&mut controller, Command::OpenSession(unknown));
        assert_eq!(controller.preferences().target_face, "default");
        command(&mut controller, Command::OpenSession(known));
        assert_eq!(controller.preferences().target_face, "air_rifle_10m");
        assert_eq!(
            load_preferences(&rig.paths.settings).target_face,
            "air_rifle_10m"
        );
    }

    #[test]
    fn saved_session_review_ignores_live_input() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        let sid = shottrainer_core::sessions::SessionRepository::new(&controller.db)
            .create_session(&Default::default())
            .unwrap();
        command(&mut controller, Command::OpenSession(sid));
        let trace_point = |rig: &TestRig, controller: &mut Controller| {
            rig.take();
            rig.detector.push(circle_at(330.0, 240.0));
            rig.camera.emit(0, frame_event(1, 20.0));
            rig.pump(controller);
            rig.take().into_iter().find_map(|e| match e {
                UiEvent::Frame(view) => Some(view.trace_point_mm),
                _ => None,
            })
        };
        assert_eq!(trace_point(&rig, &mut controller), Some(None));
        command(
            &mut controller,
            Command::StartSession {
                name: "Next".into(),
                category: "practice".into(),
            },
        );
        assert!(trace_point(&rig, &mut controller).unwrap().is_some());
    }

    #[test]
    fn replay_runs_on_the_controller_clock() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        let repo = shottrainer_core::sessions::SessionRepository::new(&controller.db);
        let sid = repo.create_session(&Default::default()).unwrap();
        repo.add_shot(
            sid,
            &shottrainer_core::sessions::NewShot {
                ts: 1.0,
                x_mm: Some(0.0),
                y_mm: Some(0.0),
                audio_level: 0.5,
                confidence: 1.0,
                score: String::new(),
            },
        )
        .unwrap();
        let sample = |ts| shottrainer_tracking::models::TrackingSample {
            x_mm: Some(0.0),
            y_mm: Some(0.0),
            ..shottrainer_tracking::models::TrackingSample::new(ts, 0.0, 0.0)
        };
        repo.append_trace(sid, &[sample(0.5), sample(0.75), sample(1.0)])
            .unwrap();
        command(&mut controller, Command::OpenSession(sid));
        command(&mut controller, Command::SelectShot(0));
        rig.set_now(100.0);
        command(&mut controller, Command::ReplayPlay);
        assert_eq!(controller.next_deadline(), Some(100.25));
        controller.tick();
        assert_eq!(controller.session().player().index(), 0, "not due yet");
        rig.set_now(100.25);
        controller.tick();
        assert_eq!(controller.session().player().index(), 1);
        assert_eq!(controller.next_deadline(), Some(100.5));
    }

    #[test]
    fn an_unknown_category_starts_a_practice_session() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        command(
            &mut controller,
            Command::StartSession {
                name: "S".into(),
                category: "bogus".into(),
            },
        );
        let id = controller.session().recorder.session_id().unwrap();
        let repo = shottrainer_core::sessions::SessionRepository::new(&controller.db);
        let saved = repo.get_session(id).unwrap().unwrap();
        assert_eq!(
            (saved.category.as_str(), saved.app_version.as_str()),
            ("practice", "9.9.9")
        );
    }

    #[test]
    fn shutdown_saves_the_recording_and_stops_the_devices() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        command(
            &mut controller,
            Command::StartSession {
                name: "S".into(),
                category: "practice".into(),
            },
        );
        rig.take();
        controller.shutdown();
        assert!(!controller.session().is_recording());
        assert!(rig.take().iter().any(|e| matches!(
            e,
            UiEvent::Session {
                state: SessionState::Idle,
                ..
            }
        )));
        assert_eq!(
            (rig.camera.state().stopped, rig.audio.state().stopped),
            (1, 1)
        );
    }

    #[test]
    fn device_and_face_lists_are_reported() {
        let rig = TestRig::new();
        rig.audio.state().inputs = vec!["default".into(), "USB Mic".into()];
        let mut controller = rig.build();
        rig.take();
        command(&mut controller, Command::ListDevices { refresh: true });
        command(&mut controller, Command::ListTargetFaces);
        let events = rig.take();
        assert_eq!(
            events[0],
            UiEvent::DeviceOptions {
                cameras: vec![(0, "Camera 0".into())],
                microphones: vec!["default".into(), "USB Mic".into()],
                saved_camera: String::new(),
            }
        );
        assert!(matches!(&events[1], UiEvent::TargetFaces(faces) if faces.len() >= 6));
    }
    /// Emits one frame on capture `start`, checks the capture's sink let it
    /// through and hands it to the controller.
    fn pump_one_frame(rig: &TestRig, controller: &mut Controller, start: usize, id: i64) {
        rig.camera.emit(start, frame_event(id, id as f64));
        assert_eq!(
            rig.forwarded.lock().unwrap().len(),
            1,
            "frame {id} was dropped at the capture thread, so the budget was not freed"
        );
        rig.pump(controller);
    }

    #[test]
    fn processed_frames_free_the_frame_budget() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        for id in 0..6 {
            pump_one_frame(&rig, &mut controller, 0, id);
        }
        assert_eq!(rig.detector.seen.lock().unwrap().len(), 6);
    }

    #[test]
    fn frames_shown_during_review_free_the_frame_budget() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        let sid = shottrainer_core::sessions::SessionRepository::new(&controller.db)
            .create_session(&Default::default())
            .unwrap();
        command(&mut controller, Command::OpenSession(sid));
        for id in 0..6 {
            pump_one_frame(&rig, &mut controller, 0, id);
        }
    }

    #[test]
    fn frames_dropped_by_the_transform_free_the_frame_budget() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        let good = controller.frames.transform().clone();
        controller
            .frames
            .set_transform(shottrainer_tracking::frame_ops::FrameTransform {
                rotation_degrees: 45,
                ..good.clone()
            });
        for id in 0..6 {
            pump_one_frame(&rig, &mut controller, 0, id);
        }
        assert!(rig.detector.seen.lock().unwrap().is_empty());
        controller.frames.set_transform(good);
        pump_one_frame(&rig, &mut controller, 0, 7);
        assert_eq!(rig.detector.seen.lock().unwrap().len(), 1);
    }

    #[test]
    fn frames_arriving_after_the_camera_stopped_free_the_frame_budget() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        rig.camera.emit(0, frame_event(0, 0.0));
        rig.camera.emit(0, frame_event(1, 1.0));
        controller.stop_camera();
        rig.pump(&mut controller);
        for id in 2..6 {
            pump_one_frame(&rig, &mut controller, 0, id);
        }
        assert!(rig.detector.seen.lock().unwrap().is_empty());
    }

    #[test]
    fn stale_frames_neither_free_nor_use_the_new_captures_budget() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        command(
            &mut controller,
            Command::SetPreferences(Preferences {
                camera_id: Some(4),
                ..Preferences::default()
            }),
        );
        rig.camera.emit(1, frame_event(1, 1.0));
        rig.camera.emit(1, frame_event(2, 2.0));
        rig.camera.emit(0, frame_event(3, 3.0));
        let mut queued = std::mem::take(&mut *rig.forwarded.lock().unwrap());
        let stale = queued.pop().unwrap();
        controller.handle(Input::Device(stale));
        rig.camera.emit(1, frame_event(4, 4.0));
        assert!(
            rig.forwarded.lock().unwrap().is_empty(),
            "a stale frame freed the new capture's budget"
        );
        for event in queued {
            controller.handle(Input::Device(event));
        }
        for id in 5..8 {
            pump_one_frame(&rig, &mut controller, 1, id);
        }
        assert_eq!(rig.detector.seen.lock().unwrap().len(), 5);
    }

    #[test]
    fn a_restarted_microphone_drops_events_of_the_failed_stream() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        rig.audio.emit(0, AudioEvent::Error("lost".into()));
        rig.pump(&mut controller);
        assert_eq!(rig.messages(), ["Audio: lost"]);
        controller.start();
        assert_eq!(rig.audio.state().started.len(), 2);
        let shot = || {
            AudioEvent::Shot(ShotEvent {
                timestamp: 1.0,
                audio_level: 0.5,
                sample_rate: 44100,
            })
        };
        rig.audio.emit(0, AudioEvent::Level(0.5));
        rig.audio.emit(0, shot());
        rig.audio.emit(0, AudioEvent::Error("late".into()));
        rig.pump(&mut controller);
        assert!(rig.take().is_empty());
        assert!(controller.session().shots().is_empty());
        rig.audio.emit(1, AudioEvent::Level(0.5));
        rig.audio.emit(1, shot());
        rig.pump(&mut controller);
        assert_eq!(rig.take()[0], UiEvent::AudioLevel(0.5));
        assert_eq!(controller.session().shots().len(), 1);
    }

    #[test]
    fn our_own_saves_are_marked_as_seen() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        command(
            &mut controller,
            Command::SetPreferences(Preferences {
                pre_shot_ms: 2000,
                ..Preferences::default()
            }),
        );
        assert!(rig.paths.settings.exists());
        assert_eq!(controller.watcher.poll(), None, "preferences save");
        std::fs::remove_file(&rig.paths.settings).unwrap();
        controller.watcher.mark_seen();
        command(&mut controller, Command::SetCircleDiameter(42.0));
        assert!(rig.paths.settings.exists());
        assert_eq!(controller.watcher.poll(), None, "diameter save");
        std::fs::remove_file(&rig.paths.settings).unwrap();
        controller.watcher.mark_seen();
        let sid = shottrainer_core::sessions::SessionRepository::new(&controller.db)
            .create_session(&shottrainer_core::sessions::NewSession {
                target_profile: "air_rifle_10m",
                ..Default::default()
            })
            .unwrap();
        command(&mut controller, Command::OpenSession(sid));
        assert!(rig.paths.settings.exists());
        assert_eq!(controller.watcher.poll(), None, "face save");
    }

    #[test]
    fn preferences_set_after_start_reach_every_service() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        rig.take();
        let prefs = Preferences {
            audio_gain: 2.0,
            shot_threshold: 0.5,
            camera_rotation: 180,
            circle_diameter_mm: 80.0,
            tracking_region_fraction: 0.5,
            invert_trace_horizontal: true,
            invert_trace_vertical: true,
            pre_shot_ms: 2000,
            post_shot_ms: 100,
            target_face: "air_rifle_10m".into(),
            ..Preferences::default()
        };
        command(&mut controller, Command::SetPreferences(prefs.clone()));
        assert_eq!(
            rig.audio.state().updates.last().unwrap().threshold,
            0.5 / 2.0
        );
        assert_eq!(controller.frames().transform().rotation_degrees, 180);
        let tracker = controller.frames().tracker();
        assert_eq!(tracker.circle_diameter_mm(), 80.0);
        assert_eq!(tracker.detector().settings().region_fraction, 0.5);
        let events = rig.take();
        let UiEvent::Preferences { rings, .. } = &events[0] else {
            panic!("expected the preferences first, got {:?}", events[0]);
        };
        let default_rings = rings_for_face(&controller.faces, "default");
        let face_rings = rings_for_face(&controller.faces, "air_rifle_10m");
        assert_ne!(face_rings, default_rings);
        assert_eq!(rings.as_slice(), face_rings);

        // Both trace axes follow the inversion once a frame is tracked.
        // 80 mm over a 60 px circle puts a 10 px offset at 13.3 mm.
        rig.detector.push(circle_at(330.0, 250.0));
        rig.camera.emit(0, frame_event(1, 1.0));
        rig.pump(&mut controller);
        let point = rig
            .take()
            .into_iter()
            .find_map(|e| match e {
                UiEvent::Frame(view) => view.trace_point_mm,
                _ => None,
            })
            .unwrap();
        assert!(
            point.0 > 0.0 && point.1 > 0.0,
            "inverted axes, got {point:?}"
        );

        // The coordinator keeps 2000 ms before and 100 ms after the shot.
        let session = &mut controller.session;
        session.buffer.clear();
        for ts in [7.9, 8.1, 9.5, 9.95, 10.05, 10.2] {
            session
                .buffer
                .append(shottrainer_tracking::models::TrackingSample::new(
                    ts, 0.0, 0.0,
                ));
        }
        let result = session.coordinator.handle_shot(
            &session.buffer,
            ShotEvent {
                timestamp: 10.0,
                audio_level: 0.5,
                sample_rate: 44100,
            },
        );
        let times: Vec<f64> = result.trace.iter().map(|s| s.timestamp).collect();
        assert_eq!(times, [8.1, 9.5, 9.95, 10.05]);
    }

    #[test]
    fn a_new_microphone_choice_applies_at_the_next_start() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        command(
            &mut controller,
            Command::SetPreferences(Preferences {
                audio_device: "USB".into(),
                ..Preferences::default()
            }),
        );
        rig.audio.emit(0, AudioEvent::Error("lost".into()));
        controller.start();
        assert_eq!(
            rig.audio.state().started[1],
            shottrainer_audio::DeviceSelector::Name("USB".into())
        );
    }
}
