//! Database setup.

use std::path::Path;

use rusqlite::{Connection, OpenFlags, OptionalExtension};

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

const SCHEMA: &str = "
CREATE TABLE IF NOT EXISTS schema_meta (
    id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    app_version VARCHAR(32) NOT NULL,
    PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    notes TEXT NOT NULL,
    target_profile VARCHAR(64) NOT NULL,
    category VARCHAR(16) NOT NULL,
    app_version VARCHAR(32) NOT NULL,
    schema_version INTEGER NOT NULL,
    pre_shot_ms INTEGER NOT NULL DEFAULT 1500,
    post_shot_ms INTEGER NOT NULL DEFAULT 800,
    release_window_ms INTEGER NOT NULL DEFAULT 250,
    shot_refractory_ms INTEGER NOT NULL DEFAULT 400,
    shot_diameter_mm REAL NOT NULL DEFAULT 4.5,
    position TEXT NOT NULL DEFAULT 'standing',
    shots_per_series INTEGER NOT NULL DEFAULT 10,
    PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS trace_samples (
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
);
CREATE INDEX IF NOT EXISTS ix_trace_session_ts ON trace_samples (session_id, ts);
CREATE TABLE IF NOT EXISTS shots (
    id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    ts FLOAT NOT NULL,
    x_mm FLOAT,
    y_mm FLOAT,
    audio_level FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    score VARCHAR(16) NOT NULL,
    series_index INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_shots_session_id ON shots (session_id);
";

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
        // The bundled SQLite is built with SQLITE_USE_URI, which the open flags
        // cannot turn off. Only names starting with `file:` are parsed as
        // URIs, so a leading `./` keeps such a name a plain relative path.
        let plain;
        let open_path = if db_path.starts_with("file:") {
            plain = format!("./{db_path}");
            plain.as_str()
        } else {
            db_path
        };
        Connection::open_with_flags(
            open_path,
            OpenFlags::SQLITE_OPEN_READ_WRITE
                | OpenFlags::SQLITE_OPEN_CREATE
                | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )?
    };
    // SQLite leaves foreign keys off by default, which stops the
    // ON DELETE CASCADE declarations from firing.
    conn.pragma_update(None, "foreign_keys", "ON")?;
    if db_path != ":memory:" {
        // The recorder commits a batch every second. WAL with NORMAL syncing
        // avoids an fsync per commit and stays consistent after a crash. A
        // power cut can lose the last committed batch.
        conn.pragma_update(None, "journal_mode", "WAL")?;
        conn.pragma_update(None, "synchronous", "NORMAL")?;
    }
    init_database(&conn)?;
    Ok(conn)
}

/// Creates any missing tables and records the schema version in a single
/// transaction. A database stamped with any other version is refused and left
/// unchanged.
pub fn init_database(conn: &Db) -> Result<(), DatabaseError> {
    let tx = conn.unchecked_transaction()?;
    conn.execute_batch(SCHEMA)?;
    let stored: Option<i64> = conn
        .query_row("SELECT version FROM schema_meta LIMIT 1", [], |row| {
            row.get(0)
        })
        .optional()?;
    match stored {
        None => {
            conn.execute(
                "INSERT INTO schema_meta (version, app_version) VALUES (?1, ?2)",
                (SCHEMA_VERSION, APP_VERSION),
            )?;
        }
        Some(version) if version == SCHEMA_VERSION => {}
        Some(version) => {
            return Err(DatabaseError::Other(format!(
                "the session database uses schema version {version}, but this version of \
                 the app supports {SCHEMA_VERSION}"
            )));
        }
    }
    tx.commit()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn file_databases_use_wal() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("sessions.db");
        let db = make_engine(path.to_str().unwrap()).unwrap();
        let mode: String = db
            .query_row("PRAGMA journal_mode", [], |row| row.get(0))
            .unwrap();
        assert_eq!(mode, "wal");
    }
}
