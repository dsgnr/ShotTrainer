//! Database creation and schema version checks.

#[cfg(unix)]
use std::path::Path;

use rusqlite::Connection;
use shottrainer_core::sessions::{
    NewSession, NewShot, SCHEMA_VERSION, SessionRepository, init_database, make_engine,
};

fn count(conn: &Connection, table: &str) -> i64 {
    conn.query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |r| r.get(0))
        .unwrap()
}

fn version(conn: &Connection) -> i64 {
    conn.query_row("SELECT version FROM schema_meta", [], |r| r.get(0))
        .unwrap()
}

fn indexes(conn: &Connection, table: &str) -> Vec<String> {
    let mut stmt = conn
        .prepare(&format!("PRAGMA index_list({table})"))
        .unwrap();
    let mut names: Vec<String> = stmt
        .query_map([], |r| r.get(1))
        .unwrap()
        .map(Result::unwrap)
        .collect();
    names.sort();
    names
}

fn tables(conn: &Connection) -> Vec<String> {
    let mut stmt = conn
        .prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        .unwrap();
    stmt.query_map([], |r| r.get(0))
        .unwrap()
        .map(Result::unwrap)
        .collect()
}

#[test]
fn fresh_file_creates_every_table_at_the_current_version() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("nested/deeper/new.db");
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    assert_eq!(count(&conn, "schema_meta"), 1);
    for table in ["sessions", "trace_samples", "shots"] {
        assert_eq!(count(&conn, table), 0);
    }
    assert_eq!(version(&conn), SCHEMA_VERSION);
    assert_eq!(indexes(&conn, "trace_samples"), ["ix_trace_session_ts"]);
    assert_eq!(indexes(&conn, "shots"), ["ix_shots_session_id"]);
}

#[test]
fn reopening_keeps_the_rows_and_the_version() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("sessions.db");
    {
        let conn = make_engine(path.to_str().unwrap()).unwrap();
        SessionRepository::new(&conn)
            .create_session(&NewSession::default())
            .unwrap();
    }
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    assert_eq!(count(&conn, "sessions"), 1);
    assert_eq!(count(&conn, "schema_meta"), 1);
    assert_eq!(version(&conn), SCHEMA_VERSION);
}

#[test]
fn an_empty_schema_meta_gains_the_version_row() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("sessions.db");
    {
        let conn = make_engine(path.to_str().unwrap()).unwrap();
        conn.execute_batch("DELETE FROM schema_meta").unwrap();
    }
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    assert_eq!(count(&conn, "schema_meta"), 1);
    assert_eq!(version(&conn), SCHEMA_VERSION);
}

#[test]
fn memory_database_enables_foreign_keys() {
    let conn = make_engine(":memory:").unwrap();
    let fk: i64 = conn
        .query_row("PRAGMA foreign_keys", [], |r| r.get(0))
        .unwrap();
    assert_eq!(fk, 1);
    assert_eq!(version(&conn), SCHEMA_VERSION);
}

#[test]
fn deleting_a_session_cascades() {
    let conn = make_engine(":memory:").unwrap();
    let repo = SessionRepository::new(&conn);
    let id = repo.create_session(&NewSession::default()).unwrap();
    repo.add_shot(
        id,
        &NewShot {
            series_index: 0,
            ts: 1.0,
            x_mm: None,
            y_mm: None,
            audio_level: 0.5,
            confidence: 1.0,
            score: "9".into(),
        },
    )
    .unwrap();
    conn.execute("INSERT INTO trace_samples (session_id, ts, x_px, y_px, confidence, frame_id) VALUES (?1, 0.5, 1.0, 2.0, 1.0, 1)", [id]).unwrap();
    conn.execute("DELETE FROM sessions WHERE id = ?1", [id])
        .unwrap();
    assert_eq!(count(&conn, "trace_samples"), 0);
    assert_eq!(count(&conn, "shots"), 0);
}

#[test]
fn a_database_with_another_version_is_refused_and_left_unchanged() {
    let dir = tempfile::tempdir().unwrap();
    for stored in [0, 2, 99] {
        let path = dir.path().join(format!("v{stored}.db"));
        Connection::open(&path)
            .unwrap()
            .execute_batch(&format!(
                "CREATE TABLE schema_meta (id INTEGER NOT NULL, version INTEGER NOT NULL,
                     app_version VARCHAR(32) NOT NULL, PRIMARY KEY (id));
                 INSERT INTO schema_meta VALUES (1, {stored}, '9.9.9');"
            ))
            .unwrap();

        let error = make_engine(path.to_str().unwrap()).unwrap_err();

        assert!(error.to_string().contains(&stored.to_string()), "{error}");
        let conn = Connection::open(&path).unwrap();
        assert_eq!(tables(&conn), ["schema_meta"]);
        assert_eq!(version(&conn), stored);
        assert!(init_database(&conn).is_err());
    }
}

#[test]
fn corrupt_file_returns_an_error() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("corrupt.db");
    std::fs::write(&path, vec![0x5a; 4096]).unwrap();
    assert!(make_engine(path.to_str().unwrap()).is_err());
}

#[test]
fn unusable_paths_return_errors() {
    let dir = tempfile::tempdir().unwrap();
    assert!(make_engine(dir.path().to_str().unwrap()).is_err());
    let file = dir.path().join("file");
    std::fs::write(&file, b"x").unwrap();
    assert!(make_engine(file.join("child.db").to_str().unwrap()).is_err());
}

// Windows file names cannot contain a colon, so the probe is Unix only.
/// Removes the probe files even when an assertion fails.
#[cfg(unix)]
struct ProbeFiles;

#[cfg(unix)]
const PROBE_URI: &str = "file:uri_flag_probe.db";
#[cfg(unix)]
const PROBE_PLAIN: &str = "uri_flag_probe.db";

#[cfg(unix)]
impl ProbeFiles {
    fn clean() {
        let _ = std::fs::remove_file(PROBE_URI);
        let _ = std::fs::remove_file(PROBE_PLAIN);
    }
}

#[cfg(unix)]
impl Drop for ProbeFiles {
    fn drop(&mut self) {
        Self::clean();
    }
}

#[cfg(unix)]
#[test]
fn file_prefixed_name_is_a_plain_path() {
    // The path itself must start with `file:` for SQLite to URI-parse it, so
    // it is relative to the test process's current directory.
    ProbeFiles::clean();
    let _guard = ProbeFiles;
    let conn = make_engine(PROBE_URI).unwrap();
    assert_eq!(version(&conn), SCHEMA_VERSION);
    assert!(Path::new(PROBE_URI).exists());
    assert!(!Path::new(PROBE_PLAIN).exists());
}
