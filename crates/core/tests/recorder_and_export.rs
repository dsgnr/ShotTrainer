//! Replay coordinator, session recorder and CSV export tests, ported from the
//! Python suite plus the extra cases for the Rust port.

use std::path::Path;

use shottrainer_core::services::exporter::export_session_csv;
use shottrainer_core::services::replay_coordinator::{
    DEFAULT_RELEASE_WINDOW_MS, ReplayCoordinator,
};
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
    let coord = ReplayCoordinator::new(&repo);
    let shots = repo.list_shots(sid).unwrap();
    let window = coord
        .shot_window(sid, shots[0].ts, 500, 500, DEFAULT_RELEASE_WINDOW_MS)
        .unwrap();
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
    let coord = ReplayCoordinator::new(&repo);
    let ts = repo.list_shots(sid).unwrap()[0].ts;

    let short = coord.shot_window(sid, ts, 1000, 200, 200).unwrap();
    let long = coord.shot_window(sid, ts, 1000, 200, 600).unwrap();
    assert!(long.release_index.unwrap() < short.release_index.unwrap());
}

#[test]
fn test_release_index_default_is_250ms() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.append_trace(sid, &samples(60, 0.05)).unwrap();
    repo.add_shot(sid, &shot_at(1.5)).unwrap();
    let coord = ReplayCoordinator::new(&repo);
    let ts = repo.list_shots(sid).unwrap()[0].ts;

    assert_eq!(DEFAULT_RELEASE_WINDOW_MS, 250);
    let default = coord
        .shot_window(sid, ts, 1000, 200, DEFAULT_RELEASE_WINDOW_MS)
        .unwrap();
    let explicit = coord.shot_window(sid, ts, 1000, 200, 250).unwrap();
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

    let window = ReplayCoordinator::new(&repo)
        .shot_window(sid, 1.0, 500, 200, DEFAULT_RELEASE_WINDOW_MS)
        .unwrap();

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
    let window = ReplayCoordinator::new(&repo)
        .shot_window(sid, 1.0, 500, 200, DEFAULT_RELEASE_WINDOW_MS)
        .unwrap();
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
        let window = ReplayCoordinator::new(&repo)
            .shot_window(sid, 1.0, 500, 500, DEFAULT_RELEASE_WINDOW_MS)
            .unwrap();
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
    let window = ReplayCoordinator::new(&repo)
        .shot_window(sid, 1.0, 500, 500, 250)
        .unwrap();
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
    let mut recorder = SessionRecorder::new(&repo, config());
    recorder.start(&named("a")).unwrap();
    let err = recorder.start(&named("b")).unwrap_err();
    assert!(matches!(err, RecorderError::AlreadyRunning));
    assert_eq!(err.to_string(), "Session already in progress");
    assert_eq!(repo.list_sessions().unwrap().len(), 1);
}

#[test]
fn test_samples_are_flushed_in_batches() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(&repo, config());
    let sid = recorder.start(&NewSession::default()).unwrap();
    for t in 0..9 {
        recorder.add_sample(rec_sample(t as f64 * 0.1)).unwrap();
    }
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
    recorder.add_sample(rec_sample(1.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 10);
}

#[test]
fn test_stop_flushes_remaining() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(&repo, config());
    let sid = recorder.start(&NewSession::default()).unwrap();
    for t in 0..3 {
        recorder.add_sample(rec_sample(t as f64 * 0.1)).unwrap();
    }
    assert_eq!(recorder.stop().unwrap(), Some(sid));
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    assert!(repo.list_sessions().unwrap()[0].ended_at.is_some());
    assert!(!recorder.is_recording());
    assert_eq!(recorder.session_id(), None);
}

#[test]
fn test_add_shot_returns_id_and_persists() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(&repo, config());
    let sid = recorder.start(&NewSession::default()).unwrap();
    recorder.add_sample(rec_sample(0.0)).unwrap();
    let shot = NewShot {
        ts: 0.5,
        x_mm: Some(1.0),
        y_mm: Some(-1.0),
        audio_level: 0.4,
        confidence: 0.8,
        score: String::new(),
    };
    assert!(recorder.add_shot(&shot).unwrap().is_some());
    let shots = repo.list_shots(sid).unwrap();
    assert_eq!(shots.len(), 1);
    assert_eq!(shots[0].x_mm, Some(1.0));
}

#[test]
fn test_no_shot_outside_session() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(&repo, config());
    assert_eq!(recorder.add_shot(&shot_at(0.0)).unwrap(), None);
    assert_eq!(recorder.stop().unwrap(), None);
}

#[test]
fn test_samples_outside_session_are_dropped() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(&repo, config());
    recorder.add_sample(rec_sample(0.0)).unwrap();
    let sid = recorder.start(&NewSession::default()).unwrap();
    recorder.stop().unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
}

#[test]
fn test_flush_by_elapsed_trace_time() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(
        &repo,
        RecorderConfig {
            flush_every: 100,
            flush_seconds: 1.0,
        },
    );
    let sid = recorder.start(&NewSession::default()).unwrap();
    recorder.add_sample(rec_sample(0.0)).unwrap();
    recorder.add_sample(rec_sample(0.9)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
    // The initial flush timestamp is 0.0, so this sample is exactly 1 s on.
    recorder.add_sample(rec_sample(1.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    // The window restarts from the flushing sample.
    recorder.add_sample(rec_sample(1.9)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    recorder.add_sample(rec_sample(2.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 5);
}

#[test]
fn test_first_sample_with_a_late_timestamp_flushes_immediately() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(&repo, config());
    let sid = recorder.start(&NewSession::default()).unwrap();
    recorder.add_sample(rec_sample(5000.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 1);
}

#[test]
fn test_add_shot_flushes_pending_samples_first() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(&repo, config());
    let sid = recorder.start(&NewSession::default()).unwrap();
    for t in 0..3 {
        recorder.add_sample(rec_sample(t as f64 * 0.1)).unwrap();
    }
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
    recorder.add_shot(&shot_at(5.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    // The shot timestamp becomes the last flush time.
    recorder.add_sample(rec_sample(14.9)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 3);
    recorder.add_sample(rec_sample(15.0)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 5);
}

#[test]
fn test_recorder_can_start_again_after_stop() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(&repo, config());
    let first = recorder.start(&named("a")).unwrap();
    recorder.add_sample(rec_sample(0.1)).unwrap();
    recorder.stop().unwrap();
    let second = recorder.start(&named("b")).unwrap();
    assert_ne!(first, second);
    assert_eq!(recorder.session_id(), Some(second));
    recorder.stop().unwrap();
    assert_eq!(repo.trace_count(first).unwrap(), 1);
    assert_eq!(repo.trace_count(second).unwrap(), 0);
}

// Exporter

fn read_rows(path: &Path) -> Vec<String> {
    let text = std::fs::read_to_string(path).unwrap();
    assert!(text.ends_with("\r\n"));
    text.split("\r\n")
        .filter(|row| !row.is_empty())
        .map(str::to_string)
        .collect()
}

#[test]
fn test_exports_two_csv_files() {
    let dir = tempfile::tempdir().unwrap();
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&named("t")).unwrap();
    repo.append_trace(
        sid,
        &[
            TrackingSample {
                x_mm: Some(1.0),
                y_mm: Some(-1.0),
                ..TrackingSample::new(0.0, 10.0, 20.0)
            },
            TrackingSample {
                x_mm: Some(1.2),
                y_mm: Some(-1.2),
                ..TrackingSample::new(0.1, 12.0, 22.0)
            },
        ],
    )
    .unwrap();
    repo.add_shot(
        sid,
        &NewShot {
            ts: 0.05,
            x_mm: Some(0.5),
            y_mm: Some(-0.5),
            audio_level: 0.4,
            confidence: 0.9,
            score: String::new(),
        },
    )
    .unwrap();

    let out = export_session_csv(&repo, sid, dir.path()).unwrap();
    assert_eq!(out.len(), 2);
    assert!(out[0].exists());
    assert!(out[1].exists());

    let rows = read_rows(&out[0]);
    assert_eq!(
        rows[0],
        "index,timestamp,x_mm,y_mm,audio_level,confidence,score"
    );
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[1], "0,0.050000,0.500,-0.500,0.4000,0.9000,");

    let rows = read_rows(&out[1]);
    assert!(rows[0].starts_with("timestamp"));
    assert_eq!(rows.len(), 3);
}

#[test]
fn test_exports_handles_no_shots() {
    let dir = tempfile::tempdir().unwrap();
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let out = export_session_csv(&repo, sid, dir.path()).unwrap();
    assert!(out.iter().all(|p| p.exists()));
    assert_eq!(read_rows(&out[0]).len(), 1);
}

#[test]
fn test_export_creates_missing_target_directory() {
    let dir = tempfile::tempdir().unwrap();
    let target = dir.path().join("a").join("b");
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let out = export_session_csv(&repo, sid, &target).unwrap();
    assert_eq!(out[0], target.join(format!("session_{sid}_shots.csv")));
    assert_eq!(out[1], target.join(format!("session_{sid}_trace.csv")));
}

const BASE64: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

fn base64(bytes: &[u8]) -> String {
    let mut out = String::new();
    for chunk in bytes.chunks(3) {
        let n = chunk
            .iter()
            .enumerate()
            .fold(0u32, |acc, (i, &b)| acc | (b as u32) << (16 - 8 * i));
        for i in 0..4 {
            if i <= chunk.len() {
                out.push(BASE64[(n >> (18 - 6 * i) & 63) as usize] as char);
            } else {
                out.push('=');
            }
        }
    }
    out
}

fn opt(value: &serde_json::Value) -> Option<f64> {
    value.as_f64()
}

#[test]
fn test_export_matches_python_bytes() {
    let golden = testkit::load_golden("export_csv");
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&named("export")).unwrap();
    for shot in golden["shots"].as_array().unwrap() {
        repo.add_shot(
            sid,
            &NewShot {
                ts: shot["ts"].as_f64().unwrap(),
                x_mm: opt(&shot["x_mm"]),
                y_mm: opt(&shot["y_mm"]),
                audio_level: shot["audio_level"].as_f64().unwrap(),
                confidence: shot["confidence"].as_f64().unwrap(),
                score: shot["score"].as_str().unwrap().to_string(),
            },
        )
        .unwrap();
    }
    let trace: Vec<TrackingSample> = golden["samples"]
        .as_array()
        .unwrap()
        .iter()
        .map(|s| TrackingSample {
            timestamp: s["timestamp"].as_f64().unwrap(),
            x_px: s["x_px"].as_f64().unwrap(),
            y_px: s["y_px"].as_f64().unwrap(),
            x_mm: opt(&s["x_mm"]),
            y_mm: opt(&s["y_mm"]),
            confidence: s["confidence"].as_f64().unwrap(),
            frame_id: s["frame_id"].as_i64().unwrap(),
        })
        .collect();
    repo.append_trace(sid, &trace).unwrap();

    let dir = tempfile::tempdir().unwrap();
    let out = export_session_csv(&repo, sid, dir.path()).unwrap();
    let files = golden["files"].as_object().unwrap();
    assert_eq!(files.len(), out.len());
    for path in &out {
        let name = path.file_name().unwrap().to_str().unwrap();
        // Python's session id is 1 as well, so the names match.
        let expected = files[name].as_str().unwrap();
        assert_eq!(base64(&std::fs::read(path).unwrap()), expected, "{name}");
    }
}

#[test]
fn test_export_quotes_fields_like_python() {
    let dir = tempfile::tempdir().unwrap();
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    for (ts, score) in [
        (1.0, "a,b"),
        (2.0, "say \"hi\""),
        (3.0, "x\ny"),
        (4.0, "plain"),
    ] {
        repo.add_shot(
            sid,
            &NewShot {
                score: score.to_string(),
                ..shot_at(ts)
            },
        )
        .unwrap();
    }
    let out = export_session_csv(&repo, sid, dir.path()).unwrap();
    let text = std::fs::read_to_string(&out[0]).unwrap();
    let expected = "index,timestamp,x_mm,y_mm,audio_level,confidence,score\r\n\
        0,1.000000,0.000,0.000,0.4000,0.9000,\"a,b\"\r\n\
        1,2.000000,0.000,0.000,0.4000,0.9000,\"say \"\"hi\"\"\"\r\n\
        2,3.000000,0.000,0.000,0.4000,0.9000,\"x\ny\"\r\n\
        3,4.000000,0.000,0.000,0.4000,0.9000,plain\r\n";
    assert_eq!(text, expected);
}

#[test]
fn test_start_resets_the_flush_clock_and_pending_samples() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let mut recorder = SessionRecorder::new(
        &repo,
        RecorderConfig {
            flush_every: 100,
            flush_seconds: 1.0,
        },
    );
    recorder.start(&NewSession::default()).unwrap();
    recorder.add_sample(rec_sample(0.5)).unwrap();
    recorder.add_shot(&shot_at(100.0)).unwrap();
    recorder.stop().unwrap();
    let sid = recorder.start(&NewSession::default()).unwrap();
    recorder.add_sample(rec_sample(1.5)).unwrap();
    assert_eq!(repo.trace_count(sid).unwrap(), 1);
}
