//! Migration tests against databases built from the committed legacy SQL.

use std::path::{Path, PathBuf};

use rusqlite::Connection;
use shottrainer_core::sessions::{SCHEMA_VERSION, make_engine};

fn legacy_sql(version: u32) -> String {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/legacy")
        .join(format!("schema_v{version}.sql"));
    std::fs::read_to_string(&path).unwrap_or_else(|err| panic!("{}: {err}", path.display()))
}

fn legacy_db(dir: &Path, version: u32) -> PathBuf {
    let path = dir.join("legacy.db");
    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(&legacy_sql(version)).unwrap();
    path
}

fn count(conn: &Connection, table: &str) -> i64 {
    conn.query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |r| r.get(0))
        .unwrap()
}

fn version(conn: &Connection) -> i64 {
    conn.query_row("SELECT version FROM schema_meta", [], |r| r.get(0))
        .unwrap()
}

type Column = (String, String, bool, Option<String>);

fn columns(conn: &Connection, table: &str) -> Vec<Column> {
    let mut stmt = conn
        .prepare(&format!("PRAGMA table_info({table})"))
        .unwrap();
    stmt.query_map([], |r| {
        Ok((r.get(1)?, r.get(2)?, r.get::<_, i64>(3)? != 0, r.get(4)?))
    })
    .unwrap()
    .map(Result::unwrap)
    .collect()
}

fn column_names(conn: &Connection, table: &str) -> Vec<String> {
    columns(conn, table).into_iter().map(|c| c.0).collect()
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

fn check_migrated(conn: &Connection, expected_categories: &[&str]) {
    assert_eq!(count(conn, "sessions"), 2);
    assert_eq!(count(conn, "trace_samples"), 5);
    assert_eq!(count(conn, "shots"), 3);
    let names = column_names(conn, "sessions");
    assert!(names.contains(&"category".to_string()));
    assert!(!names.contains(&"calibration_json".to_string()));
    assert_eq!(version(conn), SCHEMA_VERSION);
    let mut stmt = conn
        .prepare("SELECT category FROM sessions ORDER BY id")
        .unwrap();
    let categories: Vec<String> = stmt
        .query_map([], |r| r.get(0))
        .unwrap()
        .map(Result::unwrap)
        .collect();
    assert_eq!(categories, expected_categories);
    let fk: i64 = conn
        .query_row("PRAGMA foreign_keys", [], |r| r.get(0))
        .unwrap();
    assert_eq!(fk, 1);
}

#[test]
fn migrates_v1_keeping_rows() {
    let dir = tempfile::tempdir().unwrap();
    let path = legacy_db(dir.path(), 1);
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    check_migrated(&conn, &["practice", "practice"]);
    let name: String = conn
        .query_row("SELECT name FROM sessions WHERE id = 1", [], |r| r.get(0))
        .unwrap();
    assert_eq!(name, "session 1");
    let nulls: i64 = conn
        .query_row("SELECT COUNT(*) FROM shots WHERE x_mm IS NULL", [], |r| {
            r.get(0)
        })
        .unwrap();
    assert_eq!(nulls, 1);
}

#[test]
fn migrates_v2() {
    let dir = tempfile::tempdir().unwrap();
    let path = legacy_db(dir.path(), 2);
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    check_migrated(&conn, &["practice", "practice"]);
}

#[test]
fn v3_is_unchanged_and_keeps_categories() {
    let dir = tempfile::tempdir().unwrap();
    let path = legacy_db(dir.path(), 3);
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    check_migrated(&conn, &["practice", "match"]);
}

#[test]
fn reopening_a_migrated_database_is_a_no_op() {
    let dir = tempfile::tempdir().unwrap();
    let path = legacy_db(dir.path(), 1);
    drop(make_engine(path.to_str().unwrap()).unwrap());
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    check_migrated(&conn, &["practice", "practice"]);
}

#[test]
fn fresh_file_creates_every_table_at_current_version() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("nested/deeper/new.db");
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    assert_eq!(count(&conn, "schema_meta"), 1);
    for table in ["sessions", "trace_samples", "shots"] {
        assert_eq!(count(&conn, table), 0);
    }
    assert_eq!(version(&conn), 3);
    assert_eq!(indexes(&conn, "trace_samples"), ["ix_trace_session_ts"]);
    assert_eq!(indexes(&conn, "shots"), ["ix_shots_session_id"]);
}

#[test]
fn fresh_layout_matches_the_legacy_v3_layout() {
    let dir = tempfile::tempdir().unwrap();
    let fresh = make_engine(dir.path().join("fresh.db").to_str().unwrap()).unwrap();
    let legacy = Connection::open_in_memory().unwrap();
    legacy.execute_batch(&legacy_sql(3)).unwrap();
    for table in ["schema_meta", "sessions", "trace_samples", "shots"] {
        assert_eq!(columns(&fresh, table), columns(&legacy, table), "{table}");
        assert_eq!(indexes(&fresh, table), indexes(&legacy, table), "{table}");
    }
}

#[test]
fn memory_database_enables_foreign_keys() {
    let conn = make_engine(":memory:").unwrap();
    let fk: i64 = conn
        .query_row("PRAGMA foreign_keys", [], |r| r.get(0))
        .unwrap();
    assert_eq!(fk, 1);
    assert_eq!(version(&conn), 3);
}

#[test]
fn deleting_a_session_cascades() {
    let dir = tempfile::tempdir().unwrap();
    let path = legacy_db(dir.path(), 3);
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    conn.execute("DELETE FROM sessions WHERE id = 1", [])
        .unwrap();
    assert_eq!(count(&conn, "trace_samples"), 0);
    assert_eq!(count(&conn, "shots"), 1);
}

#[test]
fn empty_schema_meta_gets_the_current_version_without_migrating() {
    let dir = tempfile::tempdir().unwrap();
    let path = legacy_db(dir.path(), 1);
    Connection::open(&path)
        .unwrap()
        .execute_batch("DELETE FROM schema_meta")
        .unwrap();
    let conn = make_engine(path.to_str().unwrap()).unwrap();
    assert_eq!(version(&conn), 3);
    // Matches Python, which skips the migrations when no row exists.
    assert!(column_names(&conn, "sessions").contains(&"calibration_json".to_string()));
}

#[test]
fn failed_migration_rolls_back_every_step() {
    let dir = tempfile::tempdir().unwrap();
    let path = legacy_db(dir.path(), 1);
    // The version update runs after both schema steps and is made to fail.
    Connection::open(&path)
        .unwrap()
        .execute_batch(
            "CREATE TRIGGER block_update BEFORE UPDATE ON schema_meta
             BEGIN SELECT RAISE(ABORT, 'blocked'); END",
        )
        .unwrap();
    assert!(make_engine(path.to_str().unwrap()).is_err());
    let conn = Connection::open(&path).unwrap();
    let names = column_names(&conn, "sessions");
    assert!(names.contains(&"calibration_json".to_string()));
    assert!(!names.contains(&"category".to_string()));
    assert_eq!(version(&conn), 1);
    assert_eq!(count(&conn, "sessions"), 2);
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
