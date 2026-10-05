//! Exports a saved session, with its settings, shots and trace, to one JSON
//! file.

use std::io::Write;
use std::path::Path;

use crate::services::session_file::{
    FORMAT, SessionFile, SessionSettings, ShotRecord, TraceRecord, VERSION,
};
use crate::sessions::{DatabaseError, SessionRepository, format_datetime};

#[derive(Debug, thiserror::Error)]
pub enum ExportError {
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Database(#[from] DatabaseError),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error("session {0} does not exist")]
    Missing(i64),
}

pub fn export_session(
    repo: &SessionRepository,
    session_id: i64,
    path: &Path,
) -> Result<(), ExportError> {
    let session = repo
        .get_session(session_id)?
        .ok_or(ExportError::Missing(session_id))?;
    let file = SessionFile {
        format: FORMAT.into(),
        version: VERSION,
        session: SessionSettings {
            name: session.name,
            started_at: format_datetime(&session.started_at),
            ended_at: session.ended_at.as_ref().map(format_datetime),
            notes: session.notes,
            target_profile: session.target_profile,
            category: session.category,
            app_version: session.app_version,
            pre_shot_ms: session.pre_shot_ms,
            post_shot_ms: session.post_shot_ms,
            release_window_ms: session.release_window_ms,
            shot_refractory_ms: session.shot_refractory_ms,
            shot_diameter_mm: session.shot_diameter_mm,
            position: session.position,
            shots_per_series: session.shots_per_series,
        },
        shots: repo
            .list_shots(session_id)?
            .into_iter()
            .map(|s| ShotRecord {
                series_index: s.series_index,
                ts: s.ts,
                x_mm: s.x_mm,
                y_mm: s.y_mm,
                audio_level: s.audio_level,
                confidence: s.confidence,
                score: s.score,
            })
            .collect(),
        trace: repo
            .load_trace(session_id, None, None)?
            .into_iter()
            .map(|s| TraceRecord {
                timestamp: s.timestamp,
                x_px: s.x_px,
                y_px: s.y_px,
                x_mm: s.x_mm,
                y_mm: s.y_mm,
                confidence: s.confidence,
                frame_id: s.frame_id,
            })
            .collect(),
    };
    // Replace the target through a temporary file so a failed write cannot
    // truncate an earlier export.
    let parent = match path.parent() {
        Some(parent) if !parent.as_os_str().is_empty() => parent,
        _ => Path::new("."),
    };
    let mut tmp = tempfile::NamedTempFile::new_in(parent)?;
    tmp.write_all(&serde_json::to_vec(&file)?)?;
    tmp.persist(path).map_err(|error| error.error)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sessions::{NewSession, init_database, make_engine};

    #[test]
    fn export_replaces_the_target_and_leaves_no_temporary_file() {
        let db = make_engine(":memory:").unwrap();
        init_database(&db).unwrap();
        let repo = SessionRepository::new(&db);
        let id = repo.create_session(&NewSession::default()).unwrap();
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("session.json");
        std::fs::write(&path, "old").unwrap();

        export_session(&repo, id, &path).unwrap();

        let exported: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        assert_eq!(exported["format"], FORMAT);
        assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(), 1);

        let missing = dir.path().join("missing").join("session.json");
        assert!(export_session(&repo, id, &missing).is_err());
        assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(), 1);
    }
}
