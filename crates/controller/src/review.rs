//! Saved sessions, covering the browser actions, loading a session for review
//! and replaying a shot's trace window.

use std::path::Path;

use shottrainer_core::services::exporter::export_session_csv;
use shottrainer_core::services::replay_coordinator::shot_window;
use shottrainer_core::services::shot_stats::compute_trace_stats;
use shottrainer_core::sessions::SESSION_CATEGORIES;

use crate::events::{HoldZone, ReplayView, StatusMessage, UiEvent};
use crate::player::PlayerEvent;
use crate::session::{
    SessionContext, SessionManager, SessionState, ShotEntry, hold_trace, mapped_points_until,
};

/// What the controller must do after a session is opened.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct OpenOutcome {
    /// The face the session was recorded with, when it differs from the
    /// active one. The controller switches to it if the face exists.
    pub switch_face: Option<String>,
}

impl SessionManager {
    pub fn list_sessions(&self, cx: &SessionContext) {
        match cx.repo().list_sessions() {
            Ok(list) => (cx.emit)(UiEvent::Sessions(list)),
            Err(error) => db_warning(cx, "Could not list sessions", &error),
        }
    }

    pub fn rename_session(&self, cx: &SessionContext, id: i64, name: &str) {
        if let Err(error) = cx.repo().rename_session(id, name) {
            return db_warning(cx, "Could not rename the session", &error);
        }
        self.list_sessions(cx);
    }

    /// Only the stored category strings are accepted, as the Python dialog
    /// offers no others.
    pub fn set_session_category(&self, cx: &SessionContext, id: i64, category: &str) {
        if !SESSION_CATEGORIES.contains(&category) {
            log::warn!("Ignoring unknown session category {category:?}");
            return;
        }
        if let Err(error) = cx.repo().update_session_category(id, category) {
            return db_warning(cx, "Could not change the category", &error);
        }
        self.list_sessions(cx);
    }

    pub fn delete_session(&self, cx: &SessionContext, id: i64) {
        if let Err(error) = cx.repo().delete_session(id) {
            return db_warning(cx, "Could not delete the session", &error);
        }
        self.list_sessions(cx);
    }

    pub fn export_session(&self, cx: &SessionContext, id: i64, dir: &Path) {
        match export_session_csv(&cx.repo(), id, dir) {
            Ok(files) => cx.message(StatusMessage::info(
                format!("Wrote {} files to {}", files.len(), dir.display()),
                4000,
            )),
            Err(error) => {
                log::warn!("Could not export session {id}: {error}");
                cx.message(StatusMessage::warning(
                    format!("Could not export the session: {error}"),
                    5000,
                ));
            }
        }
    }

    /// Shows a saved session's shots for review. Refused while recording.
    pub fn open_session(&mut self, cx: &SessionContext, id: i64) -> OpenOutcome {
        if self.recorder.is_recording() {
            cx.message(StatusMessage::info(
                "Stop recording before opening a session",
                4000,
            ));
            return OpenOutcome::default();
        }
        let repo = cx.repo();
        let switch_face = match repo.get_session(id) {
            Ok(session) => session
                .map(|s| s.target_profile)
                .filter(|face| !face.is_empty() && *face != cx.prefs.target_face),
            Err(error) => {
                db_warning(cx, "Could not open the session", &error);
                return OpenOutcome::default();
            }
        };
        let shots = match repo.list_shots(id) {
            Ok(shots) => shots,
            Err(error) => {
                db_warning(cx, "Could not open the session", &error);
                return OpenOutcome::default();
            }
        };
        self.reviewing = Some(id);
        self.clear_replay(cx);
        (cx.emit)(UiEvent::Session {
            state: SessionState::Reviewing(id),
            summary: format!("Reviewing session {id}"),
        });
        self.shots = shots
            .into_iter()
            .map(|s| ShotEntry {
                timestamp: s.ts,
                x_mm: s.x_mm,
                y_mm: s.y_mm,
                score: (!s.score.is_empty()).then_some(s.score),
                shot_id: Some(s.id),
            })
            .collect();
        self.render(cx);
        OpenOutcome { switch_face }
    }

    /// Highlights the shot and, while reviewing, loads its trace window into
    /// the player with the release window and the hold zone.
    pub fn select_shot(&mut self, cx: &SessionContext, index: usize) {
        (cx.emit)(UiEvent::SelectedShot(index));
        let Some(session_id) = self.reviewing else {
            return;
        };
        let Some(shot_ts) = self.shots.get(index).map(|s| s.timestamp) else {
            return;
        };
        let prefs = cx.prefs;
        let window = match shot_window(
            &cx.repo(),
            session_id,
            shot_ts,
            i64::from(prefs.pre_shot_ms),
            i64::from(prefs.post_shot_ms),
            i64::from(prefs.release_window_ms),
        ) {
            Ok(window) => window,
            Err(error) => return db_warning(cx, "Could not load the shot trace", &error),
        };
        (cx.emit)(UiEvent::ReplayPlaying(false));
        let samples = &window.samples;
        let pre_points = mapped_points_until(samples, shot_ts);
        let hold_zone = (!pre_points.is_empty() && prefs.show_hold_zone).then(|| {
            let stats = compute_trace_stats(&pre_points);
            HoldZone {
                centre_mm: (stats.mean_x_mm, stats.mean_y_mm),
                radius_mm: stats.hold_tremor_mm,
            }
        });
        let duration_ms = match (samples.first(), samples.last()) {
            (Some(first), Some(last)) => {
                Some(((last.timestamp - first.timestamp) * 1000.0).round_ties_even() as i64)
            }
            _ => None,
        };
        (cx.emit)(UiEvent::ReplayLoaded(ReplayView {
            index,
            points: samples
                .iter()
                .map(|s| (s.x_mm.unwrap_or(0.0), s.y_mm.unwrap_or(0.0)))
                .collect(),
            release_index: window.release_index,
            split_index: window.split_index,
            duration_ms,
            hold_zone,
            enabled: !samples.is_empty(),
        }));
        let events = self.player.load(samples);
        emit_player(cx, events);
        (cx.emit)(UiEvent::HoldTrace(Some(hold_trace(pre_points))));
    }

    pub fn replay_play(&mut self, cx: &SessionContext, now: f64) {
        let events = self.player.play(now);
        emit_player(cx, events);
        (cx.emit)(UiEvent::ReplayPlaying(self.player.is_playing()));
    }

    pub fn replay_pause(&mut self, cx: &SessionContext) {
        self.player.pause();
        (cx.emit)(UiEvent::ReplayPlaying(false));
    }

    pub fn replay_reset(&mut self, cx: &SessionContext) {
        let events = self.player.stop();
        emit_player(cx, events);
        (cx.emit)(UiEvent::ReplayPlaying(false));
    }

    pub fn replay_seek(&mut self, cx: &SessionContext, fraction: f64, now: f64) {
        let events = self.player.seek_fraction(fraction, now);
        emit_player(cx, events);
    }

    /// Advances the player when its deadline has passed.
    pub fn replay_tick(&mut self, cx: &SessionContext, now: f64) {
        let events = self.player.tick(now);
        emit_player(cx, events);
    }
}

/// Forwards player events. `Finished` also resets the play button, as the
/// Python `finished` signal does.
fn emit_player(cx: &SessionContext, events: Vec<PlayerEvent>) {
    for event in events {
        let finished = event == PlayerEvent::Finished;
        (cx.emit)(UiEvent::Player(event));
        if finished {
            (cx.emit)(UiEvent::ReplayPlaying(false));
        }
    }
}

fn db_warning(cx: &SessionContext, what: &str, error: &dyn std::fmt::Display) {
    log::warn!("{what}: {error}");
    cx.message(StatusMessage::warning(format!("{what}: {error}"), 5000));
}

#[cfg(test)]
mod tests {
    use shottrainer_core::sessions::{NewSession, NewShot, SessionRepository};
    use shottrainer_tracking::models::TrackingSample;

    use super::*;
    use crate::session::tests::{Rig, entry, mapped, shot_at};

    fn add_shot(
        repo: &SessionRepository,
        sid: i64,
        ts: f64,
        xy: (Option<f64>, Option<f64>),
    ) -> i64 {
        repo.add_shot(
            sid,
            &NewShot {
                ts,
                x_mm: xy.0,
                y_mm: xy.1,
                audio_level: 0.5,
                confidence: 1.0,
                score: String::new(),
            },
        )
        .unwrap()
    }

    /// A saved session with one shot at 1.0 s and a trace from 0.0 to 2.0 s.
    fn saved_session(rig: &Rig, face: &str) -> i64 {
        let repo = rig.repo();
        let sid = repo
            .create_session(&NewSession {
                name: "Saved",
                target_profile: face,
                ..NewSession::default()
            })
            .unwrap();
        add_shot(&repo, sid, 1.0, (Some(3.0), Some(4.0)));
        repo.append_trace(
            sid,
            &[
                mapped(0.0, 0.0, 0.0),
                mapped(0.5, 1.0, 2.0),
                TrackingSample::new(0.7, 0.0, 0.0),
                mapped(1.0, 3.0, 4.0),
                mapped(2.0, 9.0, 9.0),
            ],
        )
        .unwrap();
        sid
    }

    fn find<T>(events: &[UiEvent], f: impl Fn(&UiEvent) -> Option<T>) -> Vec<T> {
        events.iter().filter_map(f).collect()
    }

    #[test]
    fn opening_a_session_lists_its_shots_for_review() {
        let rig = Rig::new();
        let sid = saved_session(&rig, "default");
        let mut mgr = SessionManager::new(&rig.prefs);
        let outcome = rig.run(|cx| mgr.open_session(cx, sid));
        assert_eq!(outcome, OpenOutcome::default());
        assert_eq!(mgr.reviewing(), Some(sid));
        assert_eq!(mgr.shots.len(), 1);
        assert_eq!(
            mgr.shots[0].score, None,
            "an empty stored score is no score"
        );
        let events = rig.take();
        assert!(events.contains(&UiEvent::ReplayCleared));
        assert!(events.contains(&UiEvent::Session {
            state: SessionState::Reviewing(sid),
            summary: format!("Reviewing session {sid}"),
        }));
    }

    #[test]
    fn opening_asks_to_switch_to_the_recorded_face() {
        let rig = Rig::new();
        let sid = saved_session(&rig, "air_rifle_10m");
        let mut mgr = SessionManager::new(&rig.prefs);
        let outcome = rig.run(|cx| mgr.open_session(cx, sid));
        assert_eq!(outcome.switch_face.as_deref(), Some("air_rifle_10m"));
    }

    #[test]
    fn opening_is_refused_while_recording() {
        let rig = Rig::new();
        let sid = saved_session(&rig, "default");
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.start(cx, "Live", "practice", "1"));
        rig.take();
        rig.run(|cx| mgr.open_session(cx, sid));
        assert_eq!(mgr.reviewing(), None);
        let texts = find(&rig.take(), |e| match e {
            UiEvent::Message(m) => Some(m.text.clone()),
            _ => None,
        });
        assert_eq!(texts, ["Stop recording before opening a session"]);
    }

    #[test]
    fn selecting_a_shot_loads_its_window_with_the_release_and_hold_zone() {
        let mut rig = Rig::new();
        rig.prefs.pre_shot_ms = 1000;
        rig.prefs.post_shot_ms = 1000;
        rig.prefs.release_window_ms = 500;
        let sid = saved_session(&rig, "default");
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| mgr.open_session(cx, sid));
        rig.take();
        rig.run(|cx| mgr.select_shot(cx, 0));
        let events = rig.take();
        assert_eq!(events[0], UiEvent::SelectedShot(0));
        assert_eq!(events[1], UiEvent::ReplayPlaying(false));
        let UiEvent::ReplayLoaded(view) = &events[2] else {
            panic!("expected the replay view, got {:?}", events[2]);
        };
        assert_eq!(
            view.points,
            [(0.0, 0.0), (1.0, 2.0), (3.0, 4.0), (9.0, 9.0)]
        );
        assert_eq!((view.release_index, view.split_index), (Some(1), Some(2)));
        assert_eq!(view.duration_ms, Some(2000));
        assert!(view.enabled);
        let zone = view.hold_zone.unwrap();
        assert!((zone.centre_mm.0 - 4.0 / 3.0).abs() < 1e-9);
        assert!((zone.centre_mm.1 - 2.0).abs() < 1e-9);
        assert_eq!(events[3], UiEvent::Player(PlayerEvent::Progress(0.0)));
        assert_eq!(
            events[4],
            UiEvent::Player(PlayerEvent::Point {
                x_mm: 0.0,
                y_mm: 0.0
            })
        );
        assert_eq!(mgr.player().len(), 4);
        assert_eq!(
            events.last(),
            Some(&UiEvent::HoldTrace(Some(hold_trace(vec![
                (0.0, 0.0),
                (1.0, 2.0),
                (3.0, 4.0)
            ]))))
        );
    }

    #[test]
    fn the_hold_zone_follows_the_preference() {
        let mut rig = Rig::new();
        rig.prefs.show_hold_zone = false;
        let sid = saved_session(&rig, "default");
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| {
            mgr.open_session(cx, sid);
            mgr.select_shot(cx, 0);
        });
        let views = find(&rig.take(), |e| match e {
            UiEvent::ReplayLoaded(v) => Some(v.hold_zone),
            _ => None,
        });
        assert_eq!(views, [None]);
    }

    #[test]
    fn selecting_without_review_or_out_of_range_only_highlights() {
        let rig = Rig::new();
        let sid = saved_session(&rig, "default");
        let mut mgr = SessionManager::new(&rig.prefs);
        mgr.shots.push(entry(1.0, Some(3.0), Some(4.0)));
        rig.run(|cx| mgr.select_shot(cx, 0));
        assert_eq!(rig.take(), [UiEvent::SelectedShot(0)]);
        rig.run(|cx| mgr.open_session(cx, sid));
        rig.take();
        rig.run(|cx| mgr.select_shot(cx, 7));
        assert_eq!(rig.take(), [UiEvent::SelectedShot(7)]);
        assert!(mgr.player().is_empty());
    }

    #[test]
    fn saved_session_review_ignores_live_shots() {
        let rig = Rig::new();
        let sid = saved_session(&rig, "default");
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| {
            mgr.open_session(cx, sid);
            mgr.select_shot(cx, 0);
        });
        let before = mgr.shots.clone();
        rig.run(|cx| mgr.on_shot(cx, shot_at(20.0)));
        assert_eq!(mgr.shots, before);
        assert_eq!(rig.repo().list_shots(sid).unwrap().len(), 1);
        rig.run(|cx| {
            mgr.start(cx, "Next", "practice", "1");
            mgr.on_shot(cx, shot_at(20.0));
        });
        assert_eq!(mgr.shots.len(), 1);
        assert_eq!(mgr.shots[0].timestamp, 20.0);
    }

    #[test]
    fn rescoring_saved_unmapped_shots_does_not_award_bullseyes() {
        let rig = Rig::new();
        let repo = rig.repo();
        let sid = repo.create_session(&NewSession::default()).unwrap();
        for xy in [
            (None, None),
            (None, Some(0.0)),
            (Some(0.0), None),
            (Some(0.0), Some(0.0)),
        ] {
            add_shot(&repo, sid, 1.0, xy);
        }
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| {
            mgr.open_session(cx, sid);
            mgr.rescore(cx);
        });
        let scores: Vec<String> = repo
            .list_shots(sid)
            .unwrap()
            .into_iter()
            .map(|s| s.score)
            .collect();
        assert_eq!(scores, ["", "", "", "X"]);
    }

    #[test]
    fn replay_controls_drive_the_player() {
        let rig = Rig::new();
        let sid = saved_session(&rig, "default");
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| {
            mgr.open_session(cx, sid);
            mgr.select_shot(cx, 0);
        });
        rig.take();
        rig.run(|cx| mgr.replay_play(cx, 100.0));
        assert!(mgr.player().is_playing());
        assert_eq!(rig.take().last(), Some(&UiEvent::ReplayPlaying(true)));
        rig.run(|cx| mgr.replay_pause(cx));
        assert!(!mgr.player().is_playing());
        rig.run(|cx| mgr.replay_seek(cx, 1.0, 100.0));
        // The default window ends 0.8 s after the shot, so 2.0 s is left out.
        assert_eq!((mgr.player().index(), mgr.player().len()), (2, 3));
        rig.run(|cx| mgr.replay_reset(cx));
        assert_eq!(mgr.player().index(), 0);
        assert_eq!(rig.take().last(), Some(&UiEvent::ReplayPlaying(false)));
    }

    #[test]
    fn finishing_playback_resets_the_play_button() {
        let rig = Rig::new();
        let sid = saved_session(&rig, "default");
        let mut mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| {
            mgr.open_session(cx, sid);
            mgr.select_shot(cx, 0);
            mgr.replay_play(cx, 0.0);
        });
        rig.take();
        while let Some(due) = mgr.player().deadline() {
            rig.run(|cx| mgr.replay_tick(cx, due));
        }
        let events = rig.take();
        let n = events.len();
        assert_eq!(
            events[n - 2..],
            [
                UiEvent::Player(PlayerEvent::Finished),
                UiEvent::ReplayPlaying(false)
            ]
        );
    }

    #[test]
    fn changing_the_display_discards_the_previous_replay() {
        for action in ["start", "open", "clear", "delete"] {
            let rig = Rig::new();
            let sid = saved_session(&rig, "default");
            let other = saved_session(&rig, "default");
            let mut mgr = SessionManager::new(&rig.prefs);
            rig.run(|cx| {
                mgr.open_session(cx, sid);
                mgr.select_shot(cx, 0);
                mgr.replay_play(cx, 0.0);
            });
            assert!(mgr.player().is_playing());
            rig.take();
            rig.run(|cx| match action {
                "start" => mgr.start(cx, "New", "practice", "1"),
                "open" => {
                    mgr.open_session(cx, other);
                }
                "clear" => mgr.clear_shots(cx),
                _ => mgr.delete_shot(cx, 0),
            });
            assert!(!mgr.player().is_playing(), "{action}");
            assert!(mgr.player().is_empty(), "{action}");
            assert!(rig.take().contains(&UiEvent::ReplayCleared), "{action}");
            rig.run(|cx| mgr.replay_play(cx, 1.0));
            assert!(
                !mgr.player().is_playing(),
                "{action}: play must not restart"
            );
            let expected = match action {
                "start" => None,
                "open" => Some(other),
                _ => Some(sid),
            };
            assert_eq!(mgr.reviewing(), expected, "{action}");
        }
    }

    #[test]
    fn browser_actions_update_the_database_and_relist() {
        let rig = Rig::new();
        let sid = saved_session(&rig, "default");
        let mgr = SessionManager::new(&rig.prefs);
        rig.run(|cx| {
            mgr.rename_session(cx, sid, "  Renamed  ");
            mgr.set_session_category(cx, sid, "match");
            mgr.set_session_category(cx, sid, "bogus");
        });
        let saved = rig.repo().get_session(sid).unwrap().unwrap();
        assert_eq!(
            (saved.name.as_str(), saved.category.as_str()),
            ("Renamed", "match")
        );
        let lists = find(&rig.take(), |e| match e {
            UiEvent::Sessions(list) => Some(list.len()),
            _ => None,
        });
        assert_eq!(lists, [1, 1], "the unknown category is ignored");
        rig.run(|cx| mgr.delete_session(cx, sid));
        assert!(rig.repo().get_session(sid).unwrap().is_none());
        assert_eq!(rig.take(), [UiEvent::Sessions(vec![])]);
    }

    #[test]
    fn export_writes_both_files() {
        let rig = Rig::new();
        let sid = saved_session(&rig, "default");
        let mgr = SessionManager::new(&rig.prefs);
        let dir = tempfile::tempdir().unwrap();
        let target = dir.path().join("out");
        rig.run(|cx| mgr.export_session(cx, sid, &target));
        assert!(target.join(format!("session_{sid}_shots.csv")).exists());
        assert!(target.join(format!("session_{sid}_trace.csv")).exists());
        let texts = find(&rig.take(), |e| match e {
            UiEvent::Message(m) => Some(m.text.clone()),
            _ => None,
        });
        assert_eq!(texts, [format!("Wrote 2 files to {}", target.display())]);
    }
}
