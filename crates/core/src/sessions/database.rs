//! Database setup and schema migrations.

use std::path::Path;

use rusqlite::{Connection, OptionalExtension};

use super::models::SCHEMA_VERSION;

#[derive(Debug, thiserror::Error)]
pub enum DatabaseError {
    #[error(transparent)]
    Sqlite(#[from] rusqlite::Error),
    #[error("{0}")]
    Other(String),
}

pub type Db = Connection;

const APP_VERSION: &str = env!("CARGO_PKG_VERSION");

const CREATE_SCHEMA_META: &str = "CREATE TABLE schema_meta (
    id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    app_version VARCHAR(32) NOT NULL,
    PRIMARY KEY (id)
)";

const CREATE_SESSIONS: &str = "CREATE TABLE sessions (
    id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    notes TEXT NOT NULL,
    target_profile VARCHAR(64) NOT NULL,
    category VARCHAR(16) NOT NULL,
    app_version VARCHAR(32) NOT NULL,
    schema_version INTEGER NOT NULL,
    PRIMARY KEY (id)
)";

const CREATE_TRACE_SAMPLES: &str = "CREATE TABLE trace_samples (
    id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    ts FLOAT NOT NULL,
    x_px FLOAT NOT NULL,
    y_px FLOAT NOT NULL,
    x_mm FLOAT,
    y_mm FLOAT,
    confidence FLOAT NOT NULL,
    frame_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE CASCADE
)";

const CREATE_SHOTS: &str = "CREATE TABLE shots (
    id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    ts FLOAT NOT NULL,
    x_mm FLOAT,
    y_mm FLOAT,
    audio_level FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    score VARCHAR(16) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE CASCADE
)";

/// Each table is created only when missing. Its indexes are created with it,
/// so an existing legacy table keeps whatever indexes it already has.
const TABLES: [(&str, &str, &[&str]); 4] = [
    ("schema_meta", CREATE_SCHEMA_META, &[]),
    ("sessions", CREATE_SESSIONS, &[]),
    (
        "trace_samples",
        CREATE_TRACE_SAMPLES,
        &["CREATE INDEX ix_trace_session_ts ON trace_samples (session_id, ts)"],
    ),
    (
        "shots",
        CREATE_SHOTS,
        &["CREATE INDEX ix_shots_session_id ON shots (session_id)"],
    ),
];

/// Opens the database at `db_path` (or `":memory:"`), turns foreign keys on
/// and runs [`init_database`]. Missing parent directories are created.
pub fn make_engine(db_path: &str) -> Result<Db, DatabaseError> {
    let conn = if db_path == ":memory:" {
        Connection::open_in_memory()?
    } else {
        if let Some(parent) = Path::new(db_path).parent()
            && !parent.as_os_str().is_empty()
        {
            std::fs::create_dir_all(parent).map_err(|err| {
                DatabaseError::Other(format!(
                    "cannot create database directory {}: {err}",
                    parent.display()
                ))
            })?;
        }
        Connection::open(db_path)?
    };
    // SQLite leaves foreign keys off by default, which stops the
    // ON DELETE CASCADE declarations from firing.
    conn.pragma_update(None, "foreign_keys", "ON")?;
    init_database(&conn)?;
    Ok(conn)
}

/// Creates any missing tables and runs pending migrations in a single
/// transaction. An empty `schema_meta` table is treated as a fresh database
/// and receives the current version without any migration.
pub fn init_database(conn: &Db) -> Result<(), DatabaseError> {
    let tx = conn.unchecked_transaction()?;
    for (name, create, indexes) in TABLES {
        if !table_exists(conn, name)? {
            conn.execute_batch(create)?;
            for index in indexes {
                conn.execute_batch(index)?;
            }
        }
    }
    let existing: Option<(i64, i64)> = conn
        .query_row("SELECT id, version FROM schema_meta LIMIT 1", [], |row| {
            Ok((row.get(0)?, row.get(1)?))
        })
        .optional()?;
    match existing {
        None => {
            conn.execute(
                "INSERT INTO schema_meta (version, app_version) VALUES (?1, ?2)",
                (SCHEMA_VERSION, APP_VERSION),
            )?;
        }
        Some((id, version)) if version != SCHEMA_VERSION => {
            apply_migrations(conn, version)?;
            conn.execute(
                "UPDATE schema_meta SET version = ?1, app_version = ?2 WHERE id = ?3",
                (SCHEMA_VERSION, APP_VERSION, id),
            )?;
        }
        Some(_) => {}
    }
    tx.commit()?;
    Ok(())
}

/// Applies the schema changes from `from_version` up to the latest as one
/// transaction. A failure rolls every step back. The `schema_meta` row is
/// left for the caller to update.
pub fn migrate(conn: &Db, from_version: i64) -> Result<(), DatabaseError> {
    let tx = conn.unchecked_transaction()?;
    apply_migrations(conn, from_version)?;
    tx.commit()?;
    Ok(())
}

fn apply_migrations(conn: &Connection, from_version: i64) -> Result<(), DatabaseError> {
    if from_version < 2 {
        drop_legacy_calibration_column(conn)?;
    }
    if from_version < 3 {
        add_session_category_column(conn)?;
    }
    Ok(())
}

fn table_exists(conn: &Connection, name: &str) -> Result<bool, DatabaseError> {
    let found: Option<i64> = conn
        .query_row(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?1",
            [name],
            |row| row.get(0),
        )
        .optional()?;
    Ok(found.is_some())
}

fn column_names(conn: &Connection, table: &str) -> Result<Vec<String>, DatabaseError> {
    let mut stmt = conn.prepare(&format!("PRAGMA table_info({table})"))?;
    let names = stmt
        .query_map([], |row| row.get::<_, String>(1))?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(names)
}

fn drop_legacy_calibration_column(conn: &Connection) -> Result<(), DatabaseError> {
    if column_names(conn, "sessions")?
        .iter()
        .any(|name| name == "calibration_json")
    {
        conn.execute_batch("ALTER TABLE sessions DROP COLUMN calibration_json")?;
        log::info!("Dropped legacy column sessions.calibration_json");
    }
    Ok(())
}

fn add_session_category_column(conn: &Connection) -> Result<(), DatabaseError> {
    if !column_names(conn, "sessions")?
        .iter()
        .any(|name| name == "category")
    {
        conn.execute_batch(
            "ALTER TABLE sessions ADD COLUMN category VARCHAR(16) NOT NULL DEFAULT 'practice'",
        )?;
        log::info!("Added column sessions.category");
    }
    Ok(())
}
