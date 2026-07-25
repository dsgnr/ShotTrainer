//! Repository tests, ported from the Python suite plus the extra cases for
//! the Rust port.

use std::collections::HashMap;
use std::sync::Mutex;
use std::time::Duration;

use proptest::prelude::*;
use shottrainer_core::sessions::{
    Db, NewSession, NewShot, SessionRepository, make_engine, parse_datetime, utc_now,
};
use shottrainer_tracking::models::TrackingSample;

fn engine() -> Db {
    make_engine(":memory:").unwrap()
}

fn sample(ts: f64, x: f64, y: f64) -> TrackingSample {
    TrackingSample {
        timestamp: ts,
        x_px: x,
        y_px: y,
        x_mm: Some(x),
        y_mm: Some(y),
        confidence: 1.0,
        frame_id: (ts * 100.0) as i64,
    }
}

fn shot(ts: f64, x: f64, y: f64, audio: f64, conf: f64, score: &str) -> NewShot {
    NewShot {
        ts,
        x_mm: Some(x),
        y_mm: Some(y),
        audio_level: audio,
        confidence: conf,
        score: score.to_string(),
    }
}

fn named(name: &str) -> NewSession<'_> {
    NewSession {
        name,
        ..NewSession::default()
    }
}

#[test]
fn test_create_and_list_sessions() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&named("evening practice")).unwrap();
    let summaries = repo.list_sessions().unwrap();
    assert_eq!(summaries.len(), 1);
    assert_eq!(summaries[0].id, sid);
    assert_eq!(summaries[0].name, "evening practice");
    assert_eq!(summaries[0].shot_count, 0);
}

#[test]
fn test_append_trace_is_batched_and_queryable() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let samples: Vec<_> = (0..50)
        .map(|t| sample(t as f64 / 10.0, t as f64, -(t as f64)))
        .collect();
    assert_eq!(repo.append_trace(sid, &samples).unwrap(), 50);
    assert_eq!(repo.trace_count(sid).unwrap(), 50);

    let loaded = repo.load_trace(sid, None, None).unwrap();
    assert_eq!(loaded.len(), 50);
    assert!((loaded[0].timestamp - 0.0).abs() < 1e-9);
    assert_eq!(loaded[49].x_px, 49.0);
}

#[test]
fn test_trace_window_query() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let samples: Vec<_> = (0..100)
        .map(|t| sample(t as f64 / 10.0, 0.0, 0.0))
        .collect();
    repo.append_trace(sid, &samples).unwrap();
    let window = repo.load_trace(sid, Some(2.0), Some(3.0)).unwrap();
    assert!(window.iter().all(|s| (2.0..=3.0).contains(&s.timestamp)));
    assert_eq!(window.len(), 11);
}

#[test]
fn test_add_and_list_shots() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.add_shot(sid, &shot(1.5, 2.0, -1.0, 0.4, 0.9, "9"))
        .unwrap();
    repo.add_shot(sid, &shot(3.2, 0.5, 0.1, 0.5, 0.85, ""))
        .unwrap();
    let shots = repo.list_shots(sid).unwrap();
    assert_eq!(shots.len(), 2);
    assert_eq!(shots[0].ts, 1.5);
    assert_eq!(shots[1].x_mm, Some(0.5));

    assert_eq!(repo.list_sessions().unwrap()[0].shot_count, 2);
}

#[test]
fn test_update_shot_scores_writes_new_labels() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let a = repo
        .add_shot(sid, &shot(1.0, 0.0, 0.0, 0.5, 1.0, "9"))
        .unwrap();
    let b = repo
        .add_shot(sid, &shot(2.0, 1.0, 1.0, 0.5, 1.0, "8"))
        .unwrap();
    let scores = HashMap::from([(a, "10".to_string()), (b, "8".to_string())]);
    assert_eq!(repo.update_shot_scores(&scores).unwrap(), 1);
    let refreshed: HashMap<i64, String> = repo
        .list_shots(sid)
        .unwrap()
        .into_iter()
        .map(|s| (s.id, s.score))
        .collect();
    assert_eq!(refreshed[&a], "10");
    assert_eq!(refreshed[&b], "8");
}

#[test]
fn test_update_shot_scores_ignores_empty_dict() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.add_shot(sid, &shot(1.0, 0.0, 0.0, 0.5, 1.0, "9"))
        .unwrap();
    assert_eq!(repo.update_shot_scores(&HashMap::new()).unwrap(), 0);
}

#[test]
fn test_delete_shot_removes_only_the_target_row() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let a = repo
        .add_shot(sid, &shot(1.0, 0.0, 0.0, 0.5, 1.0, "9"))
        .unwrap();
    let b = repo
        .add_shot(sid, &shot(2.0, 1.0, 1.0, 0.5, 1.0, "8"))
        .unwrap();
    assert!(repo.delete_shot(a).unwrap());
    let remaining = repo.list_shots(sid).unwrap();
    assert_eq!(remaining.len(), 1);
    assert_eq!(remaining[0].id, b);
}

#[test]
fn test_delete_shot_returns_false_for_missing_id() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.add_shot(sid, &shot(1.0, 0.0, 0.0, 0.5, 1.0, ""))
        .unwrap();
    assert!(!repo.delete_shot(999_999).unwrap());
}

#[test]
fn test_rename_session_writes_new_name() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&named("evening practice")).unwrap();
    assert!(repo.rename_session(sid, "club night").unwrap());
    assert_eq!(repo.list_sessions().unwrap()[0].name, "club night");
}

#[test]
fn test_rename_session_strips_whitespace() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&named("placeholder")).unwrap();
    assert!(repo.rename_session(sid, "   ").unwrap());
    assert_eq!(repo.list_sessions().unwrap()[0].name, "");
    assert!(repo.rename_session(sid, "  padded \t").unwrap());
    assert_eq!(repo.list_sessions().unwrap()[0].name, "padded");
}

#[test]
fn test_rename_session_returns_false_for_missing_id() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    assert!(!repo.rename_session(999_999, "anything").unwrap());
}

#[test]
fn test_create_session_records_category() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo
        .create_session(&NewSession {
            name: "match",
            category: "match",
            ..NewSession::default()
        })
        .unwrap();
    let summary = repo
        .list_sessions()
        .unwrap()
        .into_iter()
        .find(|s| s.id == sid)
        .unwrap();
    assert_eq!(summary.category, "match");
}

#[test]
fn test_create_session_defaults_to_practice() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&named("default")).unwrap();
    let summary = repo
        .list_sessions()
        .unwrap()
        .into_iter()
        .find(|s| s.id == sid)
        .unwrap();
    assert_eq!(summary.category, "practice");
}

#[test]
fn test_update_session_category_writes_new_value() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&named("match")).unwrap();
    assert!(repo.update_session_category(sid, "match").unwrap());
    let summary = repo
        .list_sessions()
        .unwrap()
        .into_iter()
        .find(|s| s.id == sid)
        .unwrap();
    assert_eq!(summary.category, "match");
}

#[test]
fn test_update_session_category_returns_false_for_missing_id() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    assert!(!repo.update_session_category(999_999, "match").unwrap());
}

#[test]
fn test_session_summary_includes_total_score() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&named("qual")).unwrap();
    for (ts, score) in [(0.1, "10"), (0.2, "X"), (0.3, "9")] {
        repo.add_shot(sid, &shot(ts, 0.0, 0.0, 0.4, 0.9, score))
            .unwrap();
    }
    let summary = &repo.list_sessions().unwrap()[0];
    assert_eq!(summary.shot_count, 3);
    assert!((summary.total_score - 29.0).abs() < 1e-9);
}

#[test]
fn test_session_summary_zero_for_unscored_shots() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.add_shot(sid, &shot(0.1, 0.0, 0.0, 0.4, 0.9, ""))
        .unwrap();
    let total = repo.list_sessions().unwrap()[0].total_score;
    assert_eq!(total, 0.0);
    assert!(total.is_sign_positive());
}

#[test]
fn test_session_summary_zero_for_session_without_shots_is_positive_zero() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    repo.create_session(&NewSession::default()).unwrap();
    let total = repo.list_sessions().unwrap()[0].total_score;
    assert_eq!(total.to_bits(), 0.0f64.to_bits());
}

#[test]
fn test_session_summary_negative_zero_scores_stay_positive_zero() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.add_shot(sid, &shot(0.1, 0.0, 0.0, 0.4, 0.9, "-0"))
        .unwrap();
    let total = repo.list_sessions().unwrap()[0].total_score;
    assert_eq!(total.to_bits(), 0.0f64.to_bits());
}

#[test]
fn test_delete_session_cascades() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.append_trace(sid, &[sample(0.0, 0.0, 0.0), sample(0.1, 0.0, 0.0)])
        .unwrap();
    repo.add_shot(sid, &shot(0.05, 0.0, 0.0, 0.3, 0.5, ""))
        .unwrap();
    repo.delete_session(sid).unwrap();
    assert!(repo.list_sessions().unwrap().is_empty());
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
    assert!(repo.list_shots(sid).unwrap().is_empty());
    assert!(repo.get_session(sid).unwrap().is_none());
}

#[test]
fn test_delete_session_removes_children_without_foreign_keys() {
    let db = engine();
    db.pragma_update(None, "foreign_keys", "OFF").unwrap();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let other = repo.create_session(&NewSession::default()).unwrap();
    repo.append_trace(sid, &[sample(0.0, 0.0, 0.0)]).unwrap();
    repo.append_trace(other, &[sample(0.0, 0.0, 0.0)]).unwrap();
    repo.add_shot(sid, &shot(0.05, 0.0, 0.0, 0.3, 0.5, ""))
        .unwrap();
    let kept = repo
        .add_shot(other, &shot(0.05, 0.0, 0.0, 0.3, 0.5, ""))
        .unwrap();
    repo.delete_session(sid).unwrap();
    let count = |sql: &str| -> i64 { db.query_row(sql, [], |r| r.get(0)).unwrap() };
    assert_eq!(count("SELECT COUNT(*) FROM trace_samples"), 1);
    assert_eq!(count("SELECT COUNT(*) FROM shots"), 1);
    assert_eq!(repo.list_shots(other).unwrap()[0].id, kept);
    assert_eq!(repo.trace_count(other).unwrap(), 1);
}

#[test]
fn test_delete_session_missing_id_is_a_no_op() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.delete_session(999_999).unwrap();
    assert_eq!(repo.list_sessions().unwrap().len(), 1);
    assert!(repo.get_session(sid).unwrap().is_some());
}

#[test]
fn test_end_session_records_timestamp() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.end_session(sid, None).unwrap();
    assert!(repo.list_sessions().unwrap()[0].ended_at.is_some());
}

static QUERIES: Mutex<Vec<String>> = Mutex::new(Vec::new());

fn record_query(statement: &str, _elapsed: Duration) {
    if let Ok(mut queries) = QUERIES.lock() {
        queries.push(statement.to_string());
    }
}

#[test]
fn test_list_sessions_query_count_does_not_grow_with_session_count() {
    let mut db = engine();
    {
        let repo = SessionRepository::new(&db);
        for i in 0..20 {
            let sid = repo
                .create_session(&named(&format!("session {i}")))
                .unwrap();
            for _ in 0..3 {
                repo.add_shot(sid, &shot(0.1, 0.0, 0.0, 0.5, 0.9, "9"))
                    .unwrap();
            }
        }
    }
    db.profile(Some(record_query));
    let summaries = SessionRepository::new(&db).list_sessions().unwrap();
    db.profile(None);

    let queries = QUERIES.lock().unwrap();
    let selects: Vec<_> = queries
        .iter()
        .filter(|q| q.trim_start().to_uppercase().starts_with("SELECT"))
        .collect();
    assert_eq!(summaries.len(), 20);
    assert_eq!(selects.len(), 2, "unexpected SELECTs: {selects:?}");
    assert!(summaries.iter().all(|s| s.shot_count == 3));
    assert!(
        summaries
            .iter()
            .all(|s| (s.total_score - 27.0).abs() < 1e-9)
    );
}

#[test]
fn null_millimetre_coordinates_round_trip_as_none() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let mut s = sample(1.0, 3.0, 4.0);
    s.x_mm = None;
    s.y_mm = None;
    repo.append_trace(sid, &[s]).unwrap();
    let loaded = repo.load_trace(sid, None, None).unwrap();
    assert_eq!(loaded[0].x_mm, None);
    assert_eq!(loaded[0].y_mm, None);
    assert_eq!(loaded[0].x_px, 3.0);

    repo.add_shot(
        sid,
        &NewShot {
            ts: 1.0,
            x_mm: None,
            y_mm: None,
            audio_level: 0.1,
            confidence: 0.2,
            score: String::new(),
        },
    )
    .unwrap();
    let shots = repo.list_shots(sid).unwrap();
    assert_eq!((shots[0].x_mm, shots[0].y_mm), (None, None));
    let session = repo.get_session(sid).unwrap().unwrap();
    assert_eq!(session.shots, shots);
}

#[test]
fn append_trace_with_empty_slice_returns_zero_and_writes_nothing() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    assert_eq!(repo.append_trace(sid, &[]).unwrap(), 0);
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
}

#[test]
fn append_trace_inserts_fifty_thousand_samples_ordered_by_timestamp() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    // Descending input proves the ordering comes from the query.
    let samples: Vec<_> = (0..50_000)
        .rev()
        .map(|i| sample(i as f64 / 1000.0, i as f64, 0.0))
        .collect();
    assert_eq!(repo.append_trace(sid, &samples).unwrap(), 50_000);
    assert_eq!(repo.trace_count(sid).unwrap(), 50_000);
    let loaded = repo.load_trace(sid, None, None).unwrap();
    assert_eq!(loaded.len(), 50_000);
    assert!(loaded.windows(2).all(|w| w[0].timestamp <= w[1].timestamp));
    assert_eq!(loaded[0].x_px, 0.0);
    assert_eq!(loaded[49_999].x_px, 49_999.0);
}

#[test]
fn append_trace_failure_rolls_back_the_whole_batch() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    // NaN is stored as NULL by SQLite, which violates NOT NULL on ts.
    let samples = [sample(1.0, 0.0, 0.0), sample(f64::NAN, 0.0, 0.0)];
    assert!(repo.append_trace(sid, &samples).is_err());
    assert_eq!(repo.trace_count(sid).unwrap(), 0);
}

#[test]
fn load_trace_with_only_one_bound() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let other = repo.create_session(&NewSession::default()).unwrap();
    let samples: Vec<_> = (0..10).map(|t| sample(t as f64, 0.0, 0.0)).collect();
    repo.append_trace(sid, &samples).unwrap();
    repo.append_trace(other, &samples).unwrap();
    let from = repo.load_trace(sid, Some(7.0), None).unwrap();
    assert_eq!(
        from.iter().map(|s| s.timestamp).collect::<Vec<_>>(),
        [7.0, 8.0, 9.0]
    );
    let until = repo.load_trace(sid, None, Some(2.0)).unwrap();
    assert_eq!(
        until.iter().map(|s| s.timestamp).collect::<Vec<_>>(),
        [0.0, 1.0, 2.0]
    );
    assert!(
        repo.load_trace(sid, Some(5.0), Some(4.0))
            .unwrap()
            .is_empty()
    );
}

#[test]
fn update_shot_scores_counts_only_changed_rows_and_skips_unknown_ids() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let a = repo
        .add_shot(sid, &shot(1.0, 0.0, 0.0, 0.5, 1.0, "9"))
        .unwrap();
    let b = repo
        .add_shot(sid, &shot(2.0, 0.0, 0.0, 0.5, 1.0, "8"))
        .unwrap();
    let unchanged = HashMap::from([(a, "9".to_string()), (b, "8".to_string())]);
    assert_eq!(repo.update_shot_scores(&unchanged).unwrap(), 0);
    let mixed = HashMap::from([
        (a, "9".to_string()),
        (b, String::new()),
        (999_999, "10".to_string()),
    ]);
    assert_eq!(repo.update_shot_scores(&mixed).unwrap(), 1);
    let shots = repo.list_shots(sid).unwrap();
    assert_eq!(shots[1].score, "");
}

#[test]
fn end_session_on_a_missing_id_does_nothing() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    repo.end_session(999_999, None).unwrap();
    let sessions = repo.list_sessions().unwrap();
    assert_eq!(sessions.len(), 1);
    assert_eq!(sessions[0].id, sid);
    assert!(sessions[0].ended_at.is_none());
}

#[test]
fn end_session_stores_the_given_time_truncated_to_microseconds() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    let nanos = parse_datetime("2026-01-02 03:04:05.123456")
        .unwrap()
        .checked_add_signed(chrono::Duration::nanoseconds(789))
        .unwrap();
    repo.end_session(sid, Some(nanos)).unwrap();
    let stored = repo.get_session(sid).unwrap().unwrap().ended_at.unwrap();
    assert_eq!(
        stored,
        parse_datetime("2026-01-02 03:04:05.123456").unwrap()
    );
    let text: String = db
        .query_row("SELECT ended_at FROM sessions", [], |r| r.get(0))
        .unwrap();
    assert_eq!(text, "2026-01-02 03:04:05.123456");
}

#[test]
fn created_session_has_started_at_close_to_now_and_stored_fields() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let before = utc_now();
    let sid = repo
        .create_session(&NewSession {
            name: "n",
            notes: "some notes",
            target_profile: "air-rifle",
            app_version: "1.2.3",
            category: "sighter",
        })
        .unwrap();
    let session = repo.get_session(sid).unwrap().unwrap();
    assert!(session.started_at >= before);
    assert!(session.started_at - before < chrono::Duration::seconds(5));
    assert_eq!(session.notes, "some notes");
    assert_eq!(session.target_profile, "air-rifle");
    assert_eq!(session.app_version, "1.2.3");
    assert_eq!(session.category, "sighter");
    assert_eq!(session.schema_version, 3);
    assert!(session.shots.is_empty());
    assert!(repo.get_session(sid + 1).unwrap().is_none());
}

#[test]
fn list_sessions_orders_newest_first_with_ties_in_id_order() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let a = repo.create_session(&named("a")).unwrap();
    let b = repo.create_session(&named("b")).unwrap();
    let c = repo.create_session(&named("c")).unwrap();
    let d = repo.create_session(&named("d")).unwrap();
    for (id, started) in [
        (a, "2026-01-01 00:00:00.000000"),
        (b, "2026-03-01 00:00:00.000000"),
        (c, "2026-02-01 00:00:00.000000"),
        (d, "2026-03-01 00:00:00.000000"),
    ] {
        db.execute(
            "UPDATE sessions SET started_at = ?1 WHERE id = ?2",
            rusqlite::params![started, id],
        )
        .unwrap();
    }
    let ids: Vec<_> = repo.list_sessions().unwrap().iter().map(|s| s.id).collect();
    assert_eq!(ids, [b, d, c, a]);
}

#[test]
fn unparseable_stored_datetimes_fall_back_to_the_epoch() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let good = repo.create_session(&named("good")).unwrap();
    let bad = repo.create_session(&named("bad")).unwrap();
    db.execute(
        "UPDATE sessions SET started_at = 'yesterday', ended_at = 'later' WHERE id = ?1",
        [bad],
    )
    .unwrap();
    let epoch = parse_datetime("1970-01-01 00:00:00").unwrap();
    let sessions = repo.list_sessions().unwrap();
    assert_eq!(sessions.len(), 2);
    let bad_summary = sessions.iter().find(|s| s.id == bad).unwrap();
    assert_eq!(bad_summary.started_at, epoch);
    assert_eq!(bad_summary.ended_at, Some(epoch));
    assert!(
        sessions
            .iter()
            .any(|s| s.id == good && s.started_at > epoch)
    );
    let session = repo.get_session(bad).unwrap().unwrap();
    assert_eq!(session.started_at, epoch);
    assert_eq!(session.ended_at, Some(epoch));
}

#[test]
fn non_text_stored_datetimes_fall_back_to_the_epoch() {
    let db = engine();
    let repo = SessionRepository::new(&db);
    let sid = repo.create_session(&NewSession::default()).unwrap();
    db.execute("UPDATE sessions SET started_at = 12345", [])
        .unwrap();
    let epoch = parse_datetime("1970-01-01 00:00:00").unwrap();
    assert_eq!(repo.get_session(sid).unwrap().unwrap().started_at, epoch);
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(32))]

    #[test]
    fn returned_ids_are_positive_and_distinct(sessions in 1usize..6, shots in 0usize..6) {
        let db = engine();
        let repo = SessionRepository::new(&db);
        let mut session_ids = Vec::new();
        let mut shot_ids = Vec::new();
        for _ in 0..sessions {
            let sid = repo.create_session(&NewSession::default()).unwrap();
            session_ids.push(sid);
            for _ in 0..shots {
                shot_ids.push(
                    repo.add_shot(sid, &shot(0.1, 0.0, 0.0, 0.5, 0.9, "")).unwrap(),
                );
            }
        }
        for ids in [&mut session_ids, &mut shot_ids] {
            prop_assert!(ids.iter().all(|&id| id > 0));
            let len = ids.len();
            ids.sort_unstable();
            ids.dedup();
            prop_assert_eq!(ids.len(), len);
        }
    }
}

/// The real schema declares these columns NOT NULL, so the NULLs come from a
/// copy of the tables without that constraint.
fn lenient_db() -> Db {
    let conn = Db::open_in_memory().unwrap();
    conn.execute_batch(
        "CREATE TABLE sessions (
            id INTEGER PRIMARY KEY, name TEXT, started_at DATETIME, ended_at DATETIME,
            notes TEXT, target_profile TEXT, category TEXT, app_version TEXT,
            schema_version INTEGER);
        CREATE TABLE shots (
            id INTEGER PRIMARY KEY, session_id INTEGER, ts FLOAT, x_mm FLOAT, y_mm FLOAT,
            audio_level FLOAT, confidence FLOAT, score TEXT);
        INSERT INTO sessions VALUES
            (1, NULL, '2026-01-01 10:00:00.000000', NULL, NULL, NULL, NULL, NULL, 3);
        INSERT INTO shots VALUES
            (1, 1, 1.0, 1.0, 1.0, 0.5, 0.9, NULL),
            (2, 1, 2.0, 1.0, 1.0, 0.5, 0.9, '9.5');",
    )
    .unwrap();
    conn
}

#[test]
fn list_sessions_reads_null_text_columns_as_empty() {
    let db = lenient_db();
    let sessions = SessionRepository::new(&db).list_sessions().unwrap();
    assert_eq!(sessions.len(), 1);
    assert_eq!(sessions[0].name, "");
    assert_eq!(sessions[0].category, "");
    assert_eq!(sessions[0].shot_count, 2);
    assert_eq!(sessions[0].total_score, 9.5);
}

#[test]
fn get_session_reads_null_text_columns_as_empty() {
    let db = lenient_db();
    let session = SessionRepository::new(&db).get_session(1).unwrap().unwrap();
    assert_eq!(session.name, "");
    assert_eq!(session.notes, "");
    assert_eq!(session.target_profile, "");
    assert_eq!(session.category, "");
    assert_eq!(session.app_version, "");
    let scores: Vec<&str> = session.shots.iter().map(|s| s.score.as_str()).collect();
    assert_eq!(scores, vec!["", "9.5"]);
}

#[test]
fn list_shots_reads_a_null_score_as_empty() {
    let db = lenient_db();
    let shots = SessionRepository::new(&db).list_shots(1).unwrap();
    assert_eq!(shots.len(), 2);
    assert_eq!(shots[0].score, "");
}
