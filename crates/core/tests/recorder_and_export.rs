//! Replay coordinator and session recorder tests, ported from the
//! Python suite plus the extra cases for the Rust port.

use shottrainer_core::services::replay_coordinator::{DEFAULT_RELEASE_WINDOW_MS, shot_window};
use shottrainer_core::services::session_recorder::{
    RecorderConfig, RecorderError, SessionRecorder,
};
use shottrainer_core::sessions::{Db, NewSession, NewShot, SessionRepository, make_engine};
use shottrainer_tracking::models::TrackingSample;

fn engine() -> Db {
    make_engine(":memory:").unwrap()
}

fn mapped(ts: f64, x: f64, y: f64) -> TrackingSample {
    TrackingSample {
        x_mm: Some(x),
        y_mm: Some(y),
        ..TrackingSample::new(ts, 0.0, 0.0)
    }
}

fn samples(n: usize, dt: f64) -> Vec<TrackingSample> {
    (0..n)
        .map(|i| mapped(i as f64 * dt, i as f64, -(i as f64)))
        .collect()
}

fn shot_at(ts: f64) -> NewShot {
    NewShot {
        series_index: 0,
        ts,
        x_mm: Some(0.0),
        y_mm: Some(0.0),
        audio_level: 0.4,
        confidence: 0.9,
        score: String::new(),
    }
}

// Replay coordinator

#[test]
fn test_shot_window_finds_split() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.append_trace(sid, &samples(60, 0.05)).unwrap();
    repo.add_shot(sid, &shot_at(1.0)).unwrap();
    let shots = repo.list_shots(sid).unwrap();
    let window = shot_window(&repo, sid, shots[0].ts, 500, 500, DEFAULT_RELEASE_WINDOW_MS).unwrap();
    let split = window.split_index.unwrap();
    assert!((window.samples[split].timestamp - 1.0).abs() < 0.05);
}

#[test]
fn test_release_index_respects_custom_release_ms() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.append_trace(sid, &samples(60, 0.05)).unwrap();
    repo.add_shot(sid, &shot_at(1.5)).unwrap();
    let ts = repo.list_shots(sid).unwrap()[0].ts;

    let short = shot_window(&repo, sid, ts, 1000, 200, 200).unwrap();
    let long = shot_window(&repo, sid, ts, 1000, 200, 600).unwrap();
    assert!(long.release_index.unwrap() < short.release_index.unwrap());
}

#[test]
fn test_release_index_default_is_250ms() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.append_trace(sid, &samples(60, 0.05)).unwrap();
    repo.add_shot(sid, &shot_at(1.5)).unwrap();
    let ts = repo.list_shots(sid).unwrap()[0].ts;

    assert_eq!(DEFAULT_RELEASE_WINDOW_MS, 250);
    let default = shot_window(&repo, sid, ts, 1000, 200, DEFAULT_RELEASE_WINDOW_MS).unwrap();
    let explicit = shot_window(&repo, sid, ts, 1000, 200, 250).unwrap();
    assert_eq!(default.release_index, explicit.release_index);
    assert!(default.release_index.is_some());
}

#[test]
fn test_window_indices_only_include_samples_with_both_coordinates() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let only_x = TrackingSample {
        x_mm: Some(3.0),
        ..TrackingSample::new(0.7, 0.0, 0.0)
    };
    repo.append_trace(
        sid,
        &[
            TrackingSample::new(0.5, 0.0, 0.0),
            mapped(0.6, 1.0, 2.0),
            only_x,
            mapped(0.8, 4.0, 5.0),
            mapped(1.0, 6.0, 7.0),
            mapped(1.1, 8.0, 9.0),
        ],
    )
    .unwrap();

    let window = shot_window(&repo, sid, 1.0, 500, 200, DEFAULT_RELEASE_WINDOW_MS).unwrap();

    let timestamps: Vec<f64> = window.samples.iter().map(|s| s.timestamp).collect();
    assert_eq!(timestamps, vec![0.6, 0.8, 1.0, 1.1]);
    assert_eq!(window.release_index, Some(1));
    assert_eq!(window.split_index, Some(2));
}

#[test]
fn test_unmapped_window_has_no_replay_or_release_boundaries() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.append_trace(sid, &[TrackingSample::new(1.0, 0.0, 0.0)])
        .unwrap();
    let window = shot_window(&repo, sid, 1.0, 500, 200, DEFAULT_RELEASE_WINDOW_MS).unwrap();
    assert!(window.samples.is_empty());
    assert_eq!(window.split_index, None);
    assert_eq!(window.release_index, None);
}

#[test]
fn test_missing_release_samples_do_not_mark_follow_through_as_release() {
    for timestamps in [[1.1, 1.2], [0.5, 1.1], [0.5, 0.6]] {
        let db = engine();
        let repo = SessionRepository::new(&db);
        let sid = repo.create_session(&NewSession::default()).unwrap();
        let trace: Vec<_> = timestamps.iter().map(|&ts| mapped(ts, 1.0, 2.0)).collect();
        repo.append_trace(sid, &trace).unwrap();
        let window = shot_window(&repo, sid, 1.0, 500, 500, DEFAULT_RELEASE_WINDOW_MS).unwrap();
        assert_eq!(window.release_index, None, "{timestamps:?}");
    }
}

#[test]
fn test_release_window_bounds_are_inclusive() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.append_trace(sid, &[mapped(0.75, 1.0, 1.0), mapped(1.0, 1.0, 1.0)])
        .unwrap();
    let window = shot_window(&repo, sid, 1.0, 500, 500, 250).unwrap();
    assert_eq!(window.release_index, Some(0));
    assert_eq!(window.split_index, Some(1));
}

// Session recorder

fn config() -> RecorderConfig {
    RecorderConfig {
        flush_every: 10,
        flush_seconds: 10.0,
    }
}

fn rec_sample(ts: f64) -> TrackingSample {
    TrackingSample {
        x_mm: Some(ts),
        y_mm: Some(-ts),
        ..TrackingSample::new(ts, ts * 10.0, -ts * 10.0)
    }
}

fn named(name: &str) -> NewSession<'_> {
    NewSession {
        name,
        ..NewSession::default()
    }
}

#[test]
fn test_recorder_config_defaults() {
    let config = RecorderConfig::default();
    assert_eq!(config.flush_every, 60);
    assert_eq!(config.flush_seconds, 1.0);
}

#[test]
fn test_cannot_double_start() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(config());
    recorder.start(&repo, &named("a")).unwrap();
    let err = recorder.start(&repo, &named("b")).unwrap_err();
    assert!(matches!(err, RecorderError::AlreadyRunning));
    assert_eq!(err.to_string(), "Session already in progress");
    assert_eq!(repo.list_sessions().unwrap().len(), 1);
}

#[test]
fn test_samples_are_flushed_in_batches() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(config());
    let sid = recorder.start(&repo, &NewSession::default()).unwrap();
    for t in 0..9 {
        recorder
            .add_sample(&repo, rec_sample(t as f64 * 0.1))
            .unwrap();
    }
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
    recorder.add_sample(&repo, rec_sample(1.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 10);
}

#[test]
fn test_stop_flushes_remaining() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(config());
    let sid = recorder.start(&repo, &NewSession::default()).unwrap();
    for t in 0..3 {
        recorder
            .add_sample(&repo, rec_sample(t as f64 * 0.1))
            .unwrap();
    }
    assert_eq!(recorder.stop(&repo).unwrap(), Some(sid));
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    assert!(repo.list_sessions().unwrap()[0].ended_at.is_some());
    assert!(!recorder.is_recording());
    assert_eq!(recorder.session_id(), None);
}

#[test]
fn test_add_shot_returns_id_and_persists() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(config());
    let sid = recorder.start(&repo, &NewSession::default()).unwrap();
    recorder.add_sample(&repo, rec_sample(0.0)).unwrap();
    let shot = NewShot {
        series_index: 0,
        ts: 0.5,
        x_mm: Some(1.0),
        y_mm: Some(-1.0),
        audio_level: 0.4,
        confidence: 0.8,
        score: String::new(),
    };
    assert!(recorder.add_shot(&repo, &shot).unwrap().is_some());
    let shots = repo.list_shots(sid).unwrap();
    assert_eq!(shots.len(), 1);
    assert_eq!(shots[0].x_mm, Some(1.0));
}

#[test]
fn test_no_shot_outside_session() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(config());
    assert_eq!(recorder.add_shot(&repo, &shot_at(0.0)).unwrap(), None);
    assert_eq!(recorder.stop(&repo).unwrap(), None);
}

#[test]
fn test_samples_outside_session_are_dropped() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(config());
    recorder.add_sample(&repo, rec_sample(0.0)).unwrap();
    let sid = recorder.start(&repo, &NewSession::default()).unwrap();
    recorder.stop(&repo).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
}

#[test]
fn test_flush_by_elapsed_trace_time() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(RecorderConfig {
        flush_every: 100,
        flush_seconds: 1.0,
    });
    let sid = recorder.start(&repo, &NewSession::default()).unwrap();
    recorder.add_sample(&repo, rec_sample(0.0)).unwrap();
    recorder.add_sample(&repo, rec_sample(0.9)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
    // The initial flush timestamp is 0.0, so this sample is exactly 1 s on.
    recorder.add_sample(&repo, rec_sample(1.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    // The window restarts from the flushing sample.
    recorder.add_sample(&repo, rec_sample(1.9)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    recorder.add_sample(&repo, rec_sample(2.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 5);
}

#[test]
fn test_first_sample_with_a_late_timestamp_flushes_immediately() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(config());
    let sid = recorder.start(&repo, &NewSession::default()).unwrap();
    recorder.add_sample(&repo, rec_sample(5000.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 1);
}

#[test]
fn test_add_shot_flushes_pending_samples_first() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(config());
    let sid = recorder.start(&repo, &NewSession::default()).unwrap();
    for t in 0..3 {
        recorder
            .add_sample(&repo, rec_sample(t as f64 * 0.1))
            .unwrap();
    }
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
    recorder.add_shot(&repo, &shot_at(5.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    // The shot timestamp becomes the last flush time.
    recorder.add_sample(&repo, rec_sample(14.9)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    recorder.add_sample(&repo, rec_sample(15.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 5);
}

#[test]
fn test_recorder_can_start_again_after_stop() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(config());
    let first = recorder.start(&repo, &named("a")).unwrap();
    recorder.add_sample(&repo, rec_sample(0.1)).unwrap();
    recorder.stop(&repo).unwrap();
    let second = recorder.start(&repo, &named("b")).unwrap();
    assert_ne!(first, second);
    assert_eq!(recorder.session_id(), Some(second));
    recorder.stop(&repo).unwrap();
    assert_eq!(repo.trace_count(first).unwrap(), 1);
    assert_eq!(repo.trace_count(second).unwrap(), 0);
}

#[test]
fn test_start_resets_the_flush_clock_and_pending_samples() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(RecorderConfig {
        flush_every: 100,
        flush_seconds: 1.0,
    });
    recorder.start(&repo, &NewSession::default()).unwrap();
    recorder.add_sample(&repo, rec_sample(0.5)).unwrap();
    recorder.add_shot(&repo, &shot_at(100.0)).unwrap();
    recorder.stop(&repo).unwrap();
    let sid = recorder.start(&repo, &NewSession::default()).unwrap();
    recorder.add_sample(&repo, rec_sample(1.5)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 1);
}
