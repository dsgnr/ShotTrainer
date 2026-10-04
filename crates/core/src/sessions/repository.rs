//! Persistence for sessions, trace samples and shots.

use std::collections::HashMap;

use chrono::{DateTime, NaiveDateTime};
use rusqlite::types::ValueRef;
use rusqlite::{OptionalExtension, Row, ToSql, params};
use shottrainer_tracking::models::TrackingSample;

use super::database::{DatabaseError, Db};
use super::models::{
    DEFAULT_SESSION_CATEGORY, SCHEMA_VERSION, Session, Shot, format_datetime, parse_datetime,
    truncate_to_micros, utc_now,
};
use crate::services::scoring::label_to_value;

/// A read-only view of a session for list rendering.
#[derive(Debug, Clone, PartialEq)]
pub struct SessionSummary {
    pub id: i64,
    pub name: String,
    pub started_at: NaiveDateTime,
    pub ended_at: Option<NaiveDateTime>,
    pub shot_count: i64,
    pub total_score: f64,
    pub category: String,
}

#[derive(Debug, Clone)]
pub struct NewSession<'a> {
    pub name: &'a str,
    pub notes: &'a str,
    pub target_profile: &'a str,
    pub app_version: &'a str,
    pub category: &'a str,
}

impl Default for NewSession<'_> {
    fn default() -> Self {
        NewSession {
            name: "",
            notes: "",
            target_profile: "default",
            app_version: "",
            category: DEFAULT_SESSION_CATEGORY,
        }
    }
}

#[derive(Debug, Clone)]
pub struct NewShot {
    pub ts: f64,
    pub x_mm: Option<f64>,
    pub y_mm: Option<f64>,
    pub audio_level: f64,
    pub confidence: f64,
    pub score: String,
}

pub struct SessionRepository<'a> {
    db: &'a Db,
}

impl<'a> SessionRepository<'a> {
    pub fn new(db: &'a Db) -> Self {
        SessionRepository { db }
    }

    pub fn create_session(&self, new: &NewSession) -> Result<i64, DatabaseError> {
        self.db.execute(
            "INSERT INTO sessions (name, started_at, notes, target_profile, category, \
             app_version, schema_version) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                new.name,
                format_datetime(&utc_now()),
                new.notes,
                new.target_profile,
                new.category,
                new.app_version,
                SCHEMA_VERSION
            ],
        )?;
        Ok(self.db.last_insert_rowid())
    }

    /// Stamps `ended_at` (now when `None`). Does nothing for a missing id.
    pub fn end_session(
        &self,
        session_id: i64,
        ended_at: Option<NaiveDateTime>,
    ) -> Result<(), DatabaseError> {
        let ended_at = truncate_to_micros(ended_at.unwrap_or_else(utc_now));
        self.db.execute(
            "UPDATE sessions SET ended_at = ?1 WHERE id = ?2",
            params![format_datetime(&ended_at), session_id],
        )?;
        Ok(())
    }

    /// Stores the trimmed name. Returns `false` when the session is missing.
    pub fn rename_session(&self, session_id: i64, name: &str) -> Result<bool, DatabaseError> {
        let changed = self.db.execute(
            "UPDATE sessions SET name = ?1 WHERE id = ?2",
            params![name.trim(), session_id],
        )?;
        Ok(changed > 0)
    }

    /// Unknown category values are stored verbatim.
    pub fn update_session_category(
        &self,
        session_id: i64,
        category: &str,
    ) -> Result<bool, DatabaseError> {
        let changed = self.db.execute(
            "UPDATE sessions SET category = ?1 WHERE id = ?2",
            params![category, session_id],
        )?;
        Ok(changed > 0)
    }

    /// Newest session first, with ties in id order. Shot counts and totals
    /// come from one query over all shots, so the query count does not grow
    /// with the number of sessions.
    pub fn list_sessions(&self) -> Result<Vec<SessionSummary>, DatabaseError> {
        let tx = self.db.unchecked_transaction()?;
        let mut stmt = tx.prepare(
            "SELECT id, name, started_at, ended_at, category FROM sessions \
             ORDER BY started_at DESC, id ASC",
        )?;
        let mut sessions = stmt
            .query_map([], |row| {
                Ok(SessionSummary {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    started_at: read_datetime(row, 2)?,
                    ended_at: read_optional_datetime(row, 3)?,
                    shot_count: 0,
                    total_score: 0.0,
                    category: row.get(4)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;
        if sessions.is_empty() {
            return Ok(sessions);
        }

        let index: HashMap<i64, usize> = sessions
            .iter()
            .enumerate()
            .map(|(i, s)| (s.id, i))
            .collect();
        let mut stmt = tx.prepare("SELECT session_id, score FROM shots ORDER BY id")?;
        let mut rows = stmt.query([])?;
        while let Some(row) = rows.next()? {
            let Some(&i) = index.get(&row.get::<_, i64>(0)?) else {
                continue;
            };
            let summary = &mut sessions[i];
            summary.shot_count += 1;
            if let Some(value) = label_to_value(&row.get::<_, String>(1)?) {
                summary.total_score += value;
            }
        }
        Ok(sessions)
    }

    pub fn get_session(&self, session_id: i64) -> Result<Option<Session>, DatabaseError> {
        let session = self
            .db
            .query_row(
                "SELECT id, name, started_at, ended_at, notes, target_profile, category, \
                 app_version, schema_version FROM sessions WHERE id = ?1",
                [session_id],
                |row| {
                    Ok(Session {
                        id: row.get(0)?,
                        name: row.get(1)?,
                        started_at: read_datetime(row, 2)?,
                        ended_at: read_optional_datetime(row, 3)?,
                        notes: row.get(4)?,
                        target_profile: row.get(5)?,
                        category: row.get(6)?,
                        app_version: row.get(7)?,
                        schema_version: row.get(8)?,
                        shots: Vec::new(),
                    })
                },
            )
            .optional()?;
        let Some(mut session) = session else {
            return Ok(None);
        };
        session.shots = self.shots_ordered("id", session_id)?;
        Ok(Some(session))
    }

    /// Removes the session with its trace samples and shots, whether or not
    /// foreign key cascades are enabled on the connection.
    pub fn delete_session(&self, session_id: i64) -> Result<(), DatabaseError> {
        let tx = self.db.unchecked_transaction()?;
        tx.execute(
            "DELETE FROM trace_samples WHERE session_id = ?1",
            [session_id],
        )?;
        tx.execute("DELETE FROM shots WHERE session_id = ?1", [session_id])?;
        tx.execute("DELETE FROM sessions WHERE id = ?1", [session_id])?;
        tx.commit()?;
        Ok(())
    }

    pub fn delete_shot(&self, shot_id: i64) -> Result<bool, DatabaseError> {
        let changed = self
            .db
            .execute("DELETE FROM shots WHERE id = ?1", [shot_id])?;
        Ok(changed > 0)
    }

    /// Inserts all samples in one transaction and returns the count.
    pub fn append_trace(
        &self,
        session_id: i64,
        samples: &[TrackingSample],
    ) -> Result<usize, DatabaseError> {
        if samples.is_empty() {
            return Ok(0);
        }
        let tx = self.db.unchecked_transaction()?;
        {
            let mut stmt = tx.prepare(
                "INSERT INTO trace_samples (session_id, ts, x_px, y_px, x_mm, y_mm, \
                 confidence, frame_id) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            )?;
            for s in samples {
                stmt.execute(params![
                    session_id,
                    s.timestamp,
                    s.x_px,
                    s.y_px,
                    s.x_mm,
                    s.y_mm,
                    s.confidence,
                    s.frame_id
                ])?;
            }
        }
        tx.commit()?;
        Ok(samples.len())
    }

    /// Samples ordered by timestamp. Both bounds are inclusive and optional.
    pub fn load_trace(
        &self,
        session_id: i64,
        start_ts: Option<f64>,
        end_ts: Option<f64>,
    ) -> Result<Vec<TrackingSample>, DatabaseError> {
        let mut sql = String::from(
            "SELECT ts, x_px, y_px, x_mm, y_mm, confidence, frame_id FROM trace_samples \
             WHERE session_id = ?1",
        );
        let mut args: Vec<&dyn ToSql> = vec![&session_id];
        if let Some(start) = start_ts.as_ref() {
            args.push(start);
            sql.push_str(&format!(" AND ts >= ?{}", args.len()));
        }
        if let Some(end) = end_ts.as_ref() {
            args.push(end);
            sql.push_str(&format!(" AND ts <= ?{}", args.len()));
        }
        sql.push_str(" ORDER BY ts, id");
        let mut stmt = self.db.prepare(&sql)?;
        let samples = stmt
            .query_map(args.as_slice(), |row| {
                Ok(TrackingSample {
                    timestamp: row.get(0)?,
                    x_px: row.get(1)?,
                    y_px: row.get(2)?,
                    x_mm: row.get(3)?,
                    y_mm: row.get(4)?,
                    confidence: row.get(5)?,
                    frame_id: row.get(6)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;
        Ok(samples)
    }

    pub fn trace_count(&self, session_id: i64) -> Result<i64, DatabaseError> {
        Ok(self.db.query_row(
            "SELECT COUNT(*) FROM trace_samples WHERE session_id = ?1",
            [session_id],
            |row| row.get(0),
        )?)
    }

    pub fn add_shot(&self, session_id: i64, shot: &NewShot) -> Result<i64, DatabaseError> {
        self.db.execute(
            "INSERT INTO shots (session_id, ts, x_mm, y_mm, audio_level, confidence, score) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                session_id,
                shot.ts,
                shot.x_mm,
                shot.y_mm,
                shot.audio_level,
                shot.confidence,
                shot.score
            ],
        )?;
        Ok(self.db.last_insert_rowid())
    }

    /// Shots in timestamp order, ties in id order.
    pub fn list_shots(&self, session_id: i64) -> Result<Vec<Shot>, DatabaseError> {
        self.shots_ordered("ts, id", session_id)
    }

    /// Writes new score labels and returns how many rows actually changed.
    /// Unknown ids are skipped.
    pub fn update_shot_scores(
        &self,
        scores: &HashMap<i64, String>,
    ) -> Result<usize, DatabaseError> {
        if scores.is_empty() {
            return Ok(0);
        }
        let tx = self.db.unchecked_transaction()?;
        let mut changed = 0;
        {
            let mut stmt =
                tx.prepare("UPDATE shots SET score = ?1 WHERE id = ?2 AND score != ?1")?;
            for (id, score) in scores {
                changed += stmt.execute(params![score, id])?;
            }
        }
        tx.commit()?;
        Ok(changed)
    }

    fn shots_ordered(&self, order: &str, session_id: i64) -> Result<Vec<Shot>, DatabaseError> {
        let mut stmt = self.db.prepare(&format!(
            "SELECT id, session_id, ts, x_mm, y_mm, audio_level, confidence, score \
             FROM shots WHERE session_id = ?1 ORDER BY {order}"
        ))?;
        let shots = stmt
            .query_map([session_id], |row| {
                Ok(Shot {
                    id: row.get(0)?,
                    session_id: row.get(1)?,
                    ts: row.get(2)?,
                    x_mm: row.get(3)?,
                    y_mm: row.get(4)?,
                    audio_level: row.get(5)?,
                    confidence: row.get(6)?,
                    score: row.get(7)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;
        Ok(shots)
    }
}

fn epoch() -> NaiveDateTime {
    DateTime::UNIX_EPOCH.naive_utc()
}

/// Reads a stored datetime, falling back to the Unix epoch for a value that
/// is not parseable text.
fn read_datetime(row: &Row, idx: usize) -> rusqlite::Result<NaiveDateTime> {
    Ok(read_optional_datetime(row, idx)?.unwrap_or_else(epoch))
}

fn read_optional_datetime(row: &Row, idx: usize) -> rusqlite::Result<Option<NaiveDateTime>> {
    let parsed = match row.get_ref(idx)? {
        ValueRef::Null => return Ok(None),
        ValueRef::Text(bytes) => std::str::from_utf8(bytes).ok().and_then(parse_datetime),
        _ => None,
    };
    Ok(Some(parsed.unwrap_or_else(|| {
        log::warn!("unreadable stored datetime in column {idx}, using the Unix epoch");
        epoch()
    })))
}
