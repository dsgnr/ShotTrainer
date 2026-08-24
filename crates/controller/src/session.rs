//! Port of `app/session_manager.py`, covering the live recording and the
//! on-screen shot list. Confirmation prompts belong to the front end, so a
//! clear or delete command arrives already confirmed.

use std::collections::HashMap;

use shottrainer_audio::models::ShotEvent;
use shottrainer_core::services::scoring::total_score;
use shottrainer_core::services::session_recorder::{RecorderConfig, SessionRecorder};
use shottrainer_core::services::shot_coordinator::ShotCoordinator;
use shottrainer_core::services::shot_stats::{compute_stats, compute_trace_stats};
use shottrainer_core::services::trace_buffer::TraceBuffer;
use shottrainer_core::sessions::{Db, NewSession, NewShot, SessionRepository};
use shottrainer_settings::Preferences;
use shottrainer_settings::target_faces::TargetFace;
use shottrainer_tracking::log_limit::RepeatLimiter;
use shottrainer_tracking::models::TrackingSample;

use crate::convert::{coordinator_settings, score_for};
use crate::events::{HoldTrace, ShotsView, StatusMessage, UiEvent};
use crate::player::TracePlayer;

/// The live trace buffer holds about 6.6 minutes at 30 fps, as in Python.
pub const TRACE_BUFFER_CAPACITY: usize = 12_000;

/// One shot in the on-screen list. `shot_id` is the database row when the
/// shot is saved, so re-scoring can write back to it.
#[derive(Debug, Clone, PartialEq)]
pub struct ShotEntry {
    pub timestamp: f64,
    pub x_mm: Option<f64>,
    pub y_mm: Option<f64>,
    pub score: Option<String>,
    pub shot_id: Option<i64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionState {
    Idle,
    Recording(i64),
    Reviewing(i64),
}

/// What the session manager borrows from the controller for one call.
pub struct SessionContext<'a> {
    pub db: &'a Db,
    pub prefs: &'a Preferences,
    pub faces: &'a [TargetFace],
    pub emit: &'a dyn Fn(UiEvent),
}

impl SessionContext<'_> {
    pub(crate) fn message(&self, message: StatusMessage) {
        (self.emit)(UiEvent::Message(message));
    }

    pub(crate) fn repo(&self) -> SessionRepository<'_> {
        SessionRepository::new(self.db)
    }
}

pub struct SessionManager {
    pub(crate) recorder: SessionRecorder,
    pub(crate) coordinator: ShotCoordinator,
    pub(crate) buffer: TraceBuffer,
    pub(crate) player: TracePlayer,
    pub(crate) shots: Vec<ShotEntry>,
    /// The saved session on display, if any. Live input is ignored while set.
    pub(crate) reviewing: Option<i64>,
    sample_warnings: RepeatLimiter,
}

impl SessionManager {
    pub fn new(prefs: &Preferences) -> Self {
        SessionManager {
            recorder: SessionRecorder::new(RecorderConfig::default()),
            coordinator: ShotCoordinator::new(coordinator_settings(prefs)),
            buffer: TraceBuffer::new(TRACE_BUFFER_CAPACITY),
            player: TracePlayer::new(),
            shots: Vec::new(),
            reviewing: None,
            sample_warnings: RepeatLimiter::default(),
        }
    }

    pub fn shots(&self) -> &[ShotEntry] {
        &self.shots
    }

    pub fn is_recording(&self) -> bool {
        self.recorder.is_recording()
    }

    pub fn reviewing(&self) -> Option<i64> {
        self.reviewing
    }

    pub fn player(&self) -> &TracePlayer {
        &self.player
    }

    pub fn update_settings(&mut self, prefs: &Preferences) {
        self.coordinator
            .update_settings(coordinator_settings(prefs));
    }

    /// Opens a new recording and clears the display. Ignored while recording.
    pub fn start(&mut self, cx: &SessionContext, name: &str, category: &str, app_version: &str) {
        if self.recorder.is_recording() {
            return;
        }
        self.buffer.clear();
        self.shots.clear();
        self.reviewing = None;
        self.clear_replay(cx);
        self.render(cx);
        let new = NewSession {
            name,
            target_profile: &cx.prefs.target_face,
            app_version,
            category,
            ..NewSession::default()
        };
        match self.recorder.start(&cx.repo(), &new) {
            Ok(id) => (cx.emit)(UiEvent::Session {
                state: SessionState::Recording(id),
                summary: format!("Recording session {id}"),
            }),
            Err(error) => {
                log::warn!("Could not start a session: {error}");
                cx.message(StatusMessage::warning(
                    format!("Could not start a session: {error}"),
                    5000,
                ));
            }
        }
    }

    /// Flushes and closes the recording. Ignored when not recording.
    pub fn stop(&mut self, cx: &SessionContext) {
        if !self.recorder.is_recording() {
            return;
        }
        match self.recorder.stop(&cx.repo()) {
            Ok(id) => (cx.emit)(UiEvent::Session {
                state: SessionState::Idle,
                summary: id.map_or_else(
                    || "No active session".to_owned(),
                    |id| format!("Saved session {id}"),
                ),
            }),
            Err(error) => {
                log::warn!("Could not save the session: {error}");
                cx.message(StatusMessage::warning(
                    format!("Could not save the session: {error}"),
                    5000,
                ));
            }
        }
    }

    /// Drops the on-screen list. Saved sessions are not touched.
    pub fn clear_shots(&mut self, cx: &SessionContext) {
        if self.shots.is_empty() {
            return;
        }
        self.shots.clear();
        self.clear_replay(cx);
        self.render(cx);
        cx.message(StatusMessage::info("Display cleared", 2000));
    }

    /// Removes one shot, and its database row when it has one.
    pub fn delete_shot(&mut self, cx: &SessionContext, index: usize) {
        let Some(entry) = self.shots.get(index) else {
            return;
        };
        if let Some(id) = entry.shot_id
            && let Err(error) = cx.repo().delete_shot(id)
        {
            log::warn!("Could not delete shot {id}: {error}");
            cx.message(StatusMessage::warning("Could not delete the shot", 4000));
            return;
        }
        self.shots.remove(index);
        self.clear_replay(cx);
        self.render(cx);
        cx.message(StatusMessage::info("Shot deleted", 2000));
    }

    /// Buffers a live tracking sample for shots and saves it when recording.
    pub fn on_sample(&mut self, cx: &SessionContext, sample: TrackingSample) {
        self.buffer.append(sample.clone());
        if !self.recorder.is_recording() {
            return;
        }
        match self.recorder.add_sample(&cx.repo(), sample) {
            Ok(()) => self.sample_warnings.reset(),
            Err(error) => {
                if let Some(text) = self
                    .sample_warnings
                    .check(&format!("Could not save trace samples: {error}"))
                {
                    log::warn!("{text}");
                }
            }
        }
    }

    /// Scores a detected shot, saves it when recording and lists it. Ignored
    /// while a saved session is on display.
    pub fn on_shot(&mut self, cx: &SessionContext, event: ShotEvent) {
        if self.reviewing.is_some() {
            return;
        }
        let result = self.coordinator.handle_shot(&self.buffer, event);
        let sample = result.sample.as_ref();
        let (x_mm, y_mm) = (sample.and_then(|s| s.x_mm), sample.and_then(|s| s.y_mm));
        let score = score_for(cx.faces, cx.prefs, x_mm, y_mm);
        let mut shot_id = None;
        if self.recorder.is_recording() {
            let shot = NewShot {
                ts: event.timestamp,
                x_mm,
                y_mm,
                audio_level: event.audio_level,
                confidence: sample.map_or(0.0, |s| s.confidence),
                score: score.clone(),
            };
            match self.recorder.add_shot(&cx.repo(), &shot) {
                Ok(id) => shot_id = id,
                Err(error) => {
                    log::warn!("Could not save the shot: {error}");
                    cx.message(StatusMessage::warning("Could not save the shot", 4000));
                }
            }
        }
        self.shots.push(ShotEntry {
            timestamp: event.timestamp,
            x_mm,
            y_mm,
            score: (!score.is_empty()).then_some(score),
            shot_id,
        });
        self.render(cx);
        let points = mapped_points_until(&result.trace, event.timestamp);
        (cx.emit)(UiEvent::HoldTrace(Some(hold_trace(points))));
    }

    /// Scores every listed shot again against the active face and writes
    /// the new labels of saved shots back.
    pub fn rescore(&mut self, cx: &SessionContext) {
        if self.shots.is_empty() {
            cx.message(StatusMessage::info("No shots in view to re-score", 3000));
            return;
        }
        let mut rescored = 0;
        let mut updates = HashMap::new();
        for entry in &mut self.shots {
            let score = score_for(cx.faces, cx.prefs, entry.x_mm, entry.y_mm);
            if !score.is_empty() {
                rescored += 1;
            }
            if let Some(id) = entry.shot_id {
                updates.insert(id, score.clone());
            }
            entry.score = (!score.is_empty()).then_some(score);
        }
        let persisted = if updates.is_empty() {
            0
        } else {
            cx.repo()
                .update_shot_scores(&updates)
                .unwrap_or_else(|error| {
                    log::warn!("Could not save the new scores: {error}");
                    0
                })
        };
        self.render(cx);
        let face = &cx.prefs.target_face;
        let total = self.shots.len();
        let text = if persisted > 0 {
            format!("Re-scored {rescored}/{total} shots against {face} ({persisted} saved)")
        } else {
            format!("Re-scored {rescored}/{total} shots against {face}")
        };
        cx.message(StatusMessage::info(text, 4000));
    }

    /// Unloads the replay trace and resets its controls and overlays.
    pub(crate) fn clear_replay(&mut self, cx: &SessionContext) {
        for event in self.player.load(&[]) {
            (cx.emit)(UiEvent::Player(event));
        }
        (cx.emit)(UiEvent::ReplayCleared);
    }

    /// Re-sends the header state and the shot list, for a front end that
    /// was not listening when they were first emitted. The hold figures and
    /// the replay view are not repeated.
    pub fn refresh(&self, cx: &SessionContext) {
        let (state, summary) = match (self.reviewing, self.recorder.session_id()) {
            (Some(id), _) => (
                SessionState::Reviewing(id),
                format!("Reviewing session {id}"),
            ),
            (None, Some(id)) => (
                SessionState::Recording(id),
                format!("Recording session {id}"),
            ),
            (None, None) => (SessionState::Idle, "No active session".to_owned()),
        };
        (cx.emit)(UiEvent::Session { state, summary });
        (cx.emit)(UiEvent::Shots(self.shots_view()));
    }

    fn shots_view(&self) -> ShotsView {
        let positions: Vec<(f64, f64)> = self
            .shots
            .iter()
            .filter_map(|s| Some((s.x_mm?, s.y_mm?)))
            .collect();
        ShotsView {
            shots: self.shots.clone(),
            group: compute_stats(&positions),
            total_score: total_score(self.shots.iter().map(|s| s.score.as_deref().unwrap_or(""))),
        }
    }

    /// Python `_render_shots` followed by `_refresh_stats`.
    pub(crate) fn render(&self, cx: &SessionContext) {
        (cx.emit)(UiEvent::Shots(self.shots_view()));
        (cx.emit)(UiEvent::HoldTrace(None));
    }
}

/// Mapped points at or before `until`, in trace order.
pub(crate) fn mapped_points_until(trace: &[TrackingSample], until: f64) -> Vec<(f64, f64)> {
    trace
        .iter()
        .filter(|s| s.timestamp <= until)
        .filter_map(|s| Some((s.x_mm?, s.y_mm?)))
        .collect()
}

pub(crate) fn hold_trace(points: Vec<(f64, f64)>) -> HoldTrace {
    let stats = compute_trace_stats(&points);
    HoldTrace { points, stats }
}

#[cfg(test)]
pub(crate) mod tests {
    use std::cell::RefCell;

    use shottrainer_core::sessions::make_engine;
    use shottrainer_settings::target_faces::built_in_faces;

    use super::*;

    /// A database, preferences and faces, with every emitted event kept.
    pub(crate) struct Rig {
        pub db: Db,
        pub prefs: Preferences,
        pub faces: Vec<TargetFace>,
        pub events: RefCell<Vec<UiEvent>>,
    }

    impl Rig {
        pub fn new() -> Self {
            Rig {
                db: make_engine(":memory:").unwrap(),
                prefs: Preferences::default(),
                faces: built_in_faces(),
                events: RefCell::new(Vec::new()),
            }
        }

        pub fn run<T>(&self, f: impl FnOnce(&SessionContext) -> T) -> T {
            let emit = |event| self.events.borrow_mut().push(event);
            let cx = SessionContext {
                db: &self.db,
                prefs: &self.prefs,
                faces: &self.faces,
                emit: &emit,
            };
            f(&cx)
        }

        pub fn take(&self) -> Vec<UiEvent> {
            std::mem::take(&mut *self.events.borrow_mut())
        }

        pub fn repo(&self) -> SessionRepository<'_> {
            SessionRepository::new(&self.db)
        }
    }

    pub(crate) fn mapped(timestamp: f64, x: f64, y: f64) -> TrackingSample {
        TrackingSample {
            x_mm: Some(x),
            y_mm: Some(y),
            ..TrackingSample::new(timestamp, 0.0, 0.0)
        }
    }

    pub(crate) fn shot_at(timestamp: f64) -> ShotEvent {
        ShotEvent {
            timestamp,
            audio_level: 0.5,
            sample_rate: 44100,
        }
    }

    pub(crate) fn entry(timestamp: f64, x: Option<f64>, y: Option<f64>) -> ShotEntry {
        ShotEntry {
            timestamp,
            x_mm: x,
            y_mm: y,
            score: None,
            shot_id: None,
        }
    }

    fn messages(events: &[UiEvent]) -> Vec<String> {
        events
            .iter()
            .filter_map(|e| match e {
                UiEvent::Message(m) => Some(m.text.clone()),
                _ => None,
            })
            .collect()
    }

    fn last_shots(events: &[UiEvent]) -> ShotsView {
        events
            .iter()
            .rev()
            .find_map(|e| match e {
                UiEvent::Shots(v) => Some(v.clone()),
                _ => None,
            })
            .expect("a shot list")
    }

    fn sessions(events: &[UiEvent]) -> Vec<(SessionState, String)> {
        events
            .iter()
            .filter_map(|e| match e {
                UiEvent::Session { state, summary } => Some((*state, summary.clone())),
                _ => None,
            })
            .collect()
    }

    #[test]
    fn start_clears_the_display_and_records() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        mgr.shots.push(entry(0.0, Some(1.0), Some(2.0)));
        mgr.buffer.append(mapped(0.0, 1.0, 2.0));
        mgr.reviewing = Some(9);
        rig.run(|cx| mgr.start(cx, "Test", "match", "1.0.0"));
        assert!(mgr.shots.is_empty() && mgr.buffer.is_empty());
        assert_eq!(mgr.reviewing(), None);
        let events = rig.take();
        assert!(events.contains(&UiEvent::ReplayCleared));
        let id = mgr.recorder.session_id().unwrap();
        assert_eq!(
            sessions(&events),
            [(
                SessionState::Recording(id),
                format!("Recording session {id}")
            )]
        );
        let saved = rig.repo().get_session(id).unwrap().unwrap();
        assert_eq!(
            (
                saved.name.as_str(),
                saved.category.as_str(),
                saved.app_version.as_str()
            ),
            ("Test", "match", "1.0.0")
        );
        assert_eq!(saved.target_profile, "default");
    }

    #[test]
    fn start_is_ignored_while_recording() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.start(cx, "First", "practice", "1"));
        rig.take();
        mgr.shots.push(entry(0.0, None, None));
        rig.run(|cx| mgr.start(cx, "Second", "practice", "1"));
        assert!(rig.take().is_empty());
        assert_eq!(mgr.shots.len(), 1);
        assert_eq!(rig.repo().list_sessions().unwrap().len(), 1);
    }

    #[test]
    fn stop_saves_and_is_ignored_when_idle() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.stop(cx));
        assert!(rig.take().is_empty());
        rig.run(|cx| mgr.start(cx, "S", "practice", "1"));
        let id = mgr.recorder.session_id().unwrap();
        rig.take();
        rig.run(|cx| mgr.stop(cx));
        assert!(!mgr.is_recording());
        assert_eq!(
            sessions(&rig.take()),
            [(SessionState::Idle, format!("Saved session {id}"))]
        );
        assert!(
            rig.repo()
                .get_session(id)
                .unwrap()
                .unwrap()
                .ended_at
                .is_some()
        );
    }

    #[test]
    fn a_shot_is_scored_listed_and_saved_while_recording() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.start(cx, "S", "practice", "1"));
        let id = mgr.recorder.session_id().unwrap();
        rig.run(|cx| {
            mgr.on_sample(cx, mapped(0.5, 9.0, 9.0));
            mgr.on_sample(cx, TrackingSample::new(0.7, 0.0, 0.0));
            mgr.on_sample(cx, mapped(1.0, 0.0, 0.0));
            mgr.on_sample(cx, mapped(1.1, 100.0, 100.0));
        });
        rig.take();
        rig.run(|cx| mgr.on_shot(cx, shot_at(1.0)));
        let events = rig.take();
        let saved = rig.repo().list_shots(id).unwrap();
        assert_eq!(saved.len(), 1);
        assert_eq!(
            mgr.shots,
            [ShotEntry {
                timestamp: 1.0,
                x_mm: Some(0.0),
                y_mm: Some(0.0),
                score: Some("X".into()),
                shot_id: Some(saved[0].id),
            }]
        );
        assert_eq!(saved[0].score, "X");
        assert_eq!(last_shots(&events).total_score, 10.0);
        let hold = events.iter().rev().find_map(|e| match e {
            UiEvent::HoldTrace(Some(h)) => Some(h.points.clone()),
            _ => None,
        });
        assert_eq!(hold, Some(vec![(9.0, 9.0), (0.0, 0.0)]));
        assert_eq!(
            events.last(),
            Some(&UiEvent::HoldTrace(Some(hold_trace(vec![
                (9.0, 9.0),
                (0.0, 0.0)
            ]))))
        );
    }

    #[test]
    fn a_shot_without_a_session_is_listed_but_not_saved() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.on_shot(cx, shot_at(3.0)));
        assert_eq!(mgr.shots, [entry(3.0, None, None)]);
        assert!(rig.repo().list_sessions().unwrap().is_empty());
    }

    #[test]
    fn unmapped_live_shots_remain_unscored() {
        for sample in [
            None,
            Some((None, None)),
            Some((Some(1.0), None)),
            Some((None, Some(2.0))),
        ] {
            let rig = Rig::new();
            let mut mgr = SessionManager::new(&rig.prefs);
            if let Some((x, y)) = sample {
                let s = TrackingSample {
                    x_mm: x,
                    y_mm: y,
                    ..TrackingSample::new(1.0, 1.0, 2.0)
                };
                rig.run(|cx| mgr.on_sample(cx, s));
            }
            rig.run(|cx| {
                mgr.on_shot(cx, shot_at(1.0));
                mgr.rescore(cx);
            });
            let shot = &mgr.shots[0];
            let expected = sample.unwrap_or((None, None));
            assert_eq!((shot.x_mm, shot.y_mm), expected);
            assert_eq!(shot.score, None);
            assert_eq!(last_shots(&rig.take()).group.count, 0, "{sample:?}");
        }
    }

    #[test]
    fn hold_statistics_only_use_mapped_pre_shot_points() {
        for has_pre_shot_trace in [true, false] {
            let rig = Rig::new();
            let mut mgr = SessionManager::new(&rig.prefs);
            let mut samples = vec![];
            if has_pre_shot_trace {
                samples.push(mapped(0.5, 1.0, 2.0));
                samples.push(TrackingSample::new(0.7, 0.0, 0.0));
                samples.push(mapped(1.0, 3.0, 4.0));
            }
            samples.push(mapped(1.1, 100.0, 100.0));
            rig.run(|cx| {
                for s in samples {
                    mgr.on_sample(cx, s);
                }
                mgr.on_shot(cx, shot_at(1.0));
            });
            let expected = if has_pre_shot_trace {
                vec![(1.0, 2.0), (3.0, 4.0)]
            } else {
                vec![]
            };
            assert_eq!(
                rig.take().last(),
                Some(&UiEvent::HoldTrace(Some(hold_trace(expected))))
            );
        }
    }

    #[test]
    fn live_shots_are_ignored_while_reviewing() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        mgr.reviewing = Some(1);
        rig.run(|cx| mgr.on_shot(cx, shot_at(1.0)));
        assert!(mgr.shots.is_empty());
        assert!(rig.take().is_empty());
    }

    #[test]
    fn rescore_updates_scores_and_persists_saved_shots() {
        let rig = Rig::new();
        let sid = rig.repo().create_session(&NewSession::default()).unwrap();
        let add = |x, y, score: &str| {
            rig.repo()
                .add_shot(
                    sid,
                    &NewShot {
                        ts: 0.0,
                        x_mm: Some(x),
                        y_mm: Some(y),
                        audio_level: 0.5,
                        confidence: 1.0,
                        score: score.into(),
                    },
                )
                .unwrap()
        };
        let (a, b) = (add(0.0, 0.0, "5"), add(100.0, 100.0, "9"));
        let mut mgr = SessionManager::new(&rig.prefs);
        mgr.shots = vec![
            ShotEntry {
                shot_id: Some(a),
                score: Some("5".into()),
                ..entry(0.0, Some(0.0), Some(0.0))
            },
            ShotEntry {
                shot_id: Some(b),
                score: Some("9".into()),
                ..entry(1.0, Some(100.0), Some(100.0))
            },
            entry(2.0, Some(20.0), Some(0.0)),
        ];
        rig.run(|cx| mgr.rescore(cx));
        let scores: Vec<_> = mgr.shots.iter().map(|s| s.score.clone()).collect();
        assert_eq!(scores, [Some("X".into()), None, Some("7".into())]);
        let saved: Vec<String> = rig
            .repo()
            .list_shots(sid)
            .unwrap()
            .into_iter()
            .map(|s| s.score)
            .collect();
        assert_eq!(saved, ["X", ""]);
        assert_eq!(
            messages(&rig.take()),
            ["Re-scored 2/3 shots against default (2 saved)"]
        );
    }

    #[test]
    fn rescore_without_saved_shots_does_not_touch_the_database() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        mgr.shots = vec![entry(0.0, Some(0.0), Some(0.0))];
        rig.run(|cx| mgr.rescore(cx));
        assert_eq!(
            messages(&rig.take()),
            ["Re-scored 1/1 shots against default"]
        );
    }

    #[test]
    fn rescore_with_no_shots_only_says_so() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.rescore(cx));
        assert_eq!(messages(&rig.take()), ["No shots in view to re-score"]);
    }

    #[test]
    fn delete_removes_the_entry_and_its_row() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| {
            mgr.start(cx, "S", "practice", "1");
            mgr.on_shot(cx, shot_at(0.0));
            mgr.on_shot(cx, shot_at(1.0));
        });
        let sid = mgr.recorder.session_id().unwrap();
        let keep = mgr.shots[1].shot_id;
        rig.take();
        rig.run(|cx| mgr.delete_shot(cx, 0));
        assert_eq!(mgr.shots.len(), 1);
        assert_eq!(mgr.shots[0].shot_id, keep);
        assert_eq!(rig.repo().list_shots(sid).unwrap().len(), 1);
        let events = rig.take();
        assert!(events.contains(&UiEvent::ReplayCleared));
        assert_eq!(messages(&events), ["Shot deleted"]);
    }

    #[test]
    fn delete_ignores_an_out_of_range_index() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.delete_shot(cx, 5));
        assert!(rig.take().is_empty());
    }

    #[test]
    fn clear_drops_the_list_but_not_saved_rows() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.clear_shots(cx));
        assert!(rig.take().is_empty(), "nothing to clear");
        rig.run(|cx| {
            mgr.start(cx, "S", "practice", "1");
            mgr.on_shot(cx, shot_at(0.0));
        });
        let sid = mgr.recorder.session_id().unwrap();
        rig.take();
        rig.run(|cx| mgr.clear_shots(cx));
        assert!(mgr.shots.is_empty());
        assert_eq!(rig.repo().list_shots(sid).unwrap().len(), 1);
        assert_eq!(messages(&rig.take()), ["Display cleared"]);
    }

    #[test]
    fn a_failing_database_does_not_stop_live_tracking() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.start(cx, "S", "practice", "1"));
        rig.db.execute_batch("DROP TABLE trace_samples").unwrap();
        rig.take();
        rig.run(|cx| {
            for i in 0..200 {
                mgr.on_sample(cx, mapped(f64::from(i) * 0.01, 0.0, 0.0));
            }
            mgr.on_shot(cx, shot_at(1.0));
        });
        assert_eq!(mgr.buffer.len(), 200);
        assert_eq!(mgr.shots.len(), 1);
        assert_eq!(mgr.shots[0].shot_id, None);
        assert_eq!(messages(&rig.take()), ["Could not save the shot"]);
    }

    #[test]
    fn samples_are_buffered_always_and_saved_only_while_recording() {
        let rig = Rig::new();
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.on_sample(cx, mapped(0.0, 1.0, 1.0)));
        assert_eq!(mgr.buffer.len(), 1);
        rig.run(|cx| {
            mgr.start(cx, "S", "practice", "1");
            mgr.on_sample(cx, mapped(2.0, 1.0, 1.0));
            mgr.stop(cx);
        });
        let sid = rig.repo().list_sessions().unwrap()[0].id;
        assert_eq!(rig.repo().trace_count(sid).unwrap(), 1);
    }
}
