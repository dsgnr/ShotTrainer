//! Imports a session file written by the exporter.

use std::io::Read;
use std::path::Path;

use chrono::NaiveDateTime;
use shottrainer_tracking::models::TrackingSample;

use crate::services::session_file::{FORMAT, SessionFile, VERSION};
use crate::sessions::{
    DatabaseError, Db, NewSession, NewShot, SESSION_CATEGORIES, SessionRepository, parse_datetime,
};

#[derive(Debug, thiserror::Error)]
pub enum ImportError {
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Database(#[from] DatabaseError),
    #[error("Invalid session file: {0}")]
    Invalid(String),
}

/// Larger than any session the application records, so only a wrong or
/// hostile file reaches it.
const MAX_FILE_BYTES: u64 = 256 * 1024 * 1024;

/// The column widths in the schema, which SQLite does not enforce.
const MAX_NAME_CHARS: usize = 120;
const MAX_SCORE_CHARS: usize = 16;

pub fn import_session(db: &Db, path: &Path) -> Result<i64, ImportError> {
    let mut bytes = Vec::new();
    std::fs::File::open(path)?
        .take(MAX_FILE_BYTES + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_FILE_BYTES {
        return Err(ImportError::Invalid("file is too large".into()));
    }
    let file: SessionFile =
        serde_json::from_slice(&bytes).map_err(|error| ImportError::Invalid(error.to_string()))?;
    if file.format != FORMAT {
        return Err(ImportError::Invalid("not a ShotTrainer session".into()));
    }
    if file.version != VERSION {
        return Err(ImportError::Invalid(format!(
            "unsupported version {}",
            file.version
        )));
    }
    let s = &file.session;
    if !SESSION_CATEGORIES.contains(&s.category.as_str()) {
        return Err(ImportError::Invalid(format!(
            "unknown category {:?}",
            s.category
        )));
    }
    let timings = [
        s.pre_shot_ms,
        s.post_shot_ms,
        s.release_window_ms,
        s.shot_refractory_ms,
    ];
    if timings.iter().any(|ms| *ms < 0)
        || s.shots_per_series < 1
        || !(s.shot_diameter_mm.is_finite() && s.shot_diameter_mm > 0.0)
        || file.shots.iter().any(|shot| shot.series_index < 0)
        || s.name.chars().count() > MAX_NAME_CHARS
        || file
            .shots
            .iter()
            .any(|shot| shot.score.chars().count() > MAX_SCORE_CHARS)
    {
        return Err(ImportError::Invalid("value out of range".into()));
    }
    let started_at = datetime(&s.started_at)?;
    let ended_at = s.ended_at.as_deref().map(datetime).transpose()?;

    let shots: Vec<NewShot> = file
        .shots
        .iter()
        .map(|shot| NewShot {
            series_index: shot.series_index,
            ts: shot.ts,
            x_mm: shot.x_mm,
            y_mm: shot.y_mm,
            audio_level: shot.audio_level,
            confidence: shot.confidence,
            score: shot.score.clone(),
        })
        .collect();
    let trace: Vec<TrackingSample> = file
        .trace
        .iter()
        .map(|t| TrackingSample {
            timestamp: t.timestamp,
            x_px: t.x_px,
            y_px: t.y_px,
            x_mm: t.x_mm,
            y_mm: t.y_mm,
            confidence: t.confidence,
            frame_id: t.frame_id,
        })
        .collect();
    Ok(SessionRepository::new(db).import_session(
        &NewSession {
            name: &s.name,
            notes: &s.notes,
            target_profile: &s.target_profile,
            app_version: &s.app_version,
            category: &s.category,
            pre_shot_ms: s.pre_shot_ms,
            post_shot_ms: s.post_shot_ms,
            release_window_ms: s.release_window_ms,
            shot_refractory_ms: s.shot_refractory_ms,
            shot_diameter_mm: s.shot_diameter_mm,
            position: &s.position,
            shots_per_series: s.shots_per_series,
        },
        &shots,
        &trace,
        started_at,
        ended_at,
    )?)
}

fn datetime(text: &str) -> Result<NaiveDateTime, ImportError> {
    parse_datetime(text).ok_or_else(|| ImportError::Invalid(format!("invalid datetime {text:?}")))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::services::exporter::export_session;
    use crate::sessions::{init_database, make_engine};

    fn db() -> Db {
        let db = make_engine(":memory:").unwrap();
        init_database(&db).unwrap();
        db
    }

    #[test]
    fn exported_session_round_trips_with_settings_shots_and_trace() {
        let db = db();
        let repo = SessionRepository::new(&db);
        let id = repo
            .create_session(&NewSession {
                name: "Match",
                notes: "windy",
                target_profile: "air-rifle",
                category: "match",
                pre_shot_ms: 1000,
                shot_diameter_mm: 5.6,
                position: "kneeling",
                shots_per_series: 5,
                ..NewSession::default()
            })
            .unwrap();
        repo.add_shot(
            id,
            &NewShot {
                series_index: 0,
                ts: 2.5,
                x_mm: None,
                y_mm: Some(1.25),
                audio_level: 0.8,
                confidence: 0.9,
                score: "X,\"quoted\"\nscore".into(),
            },
        )
        .unwrap();
        let sample = TrackingSample {
            timestamp: 2.4,
            x_px: 5.0,
            y_px: 6.0,
            x_mm: None,
            y_mm: Some(1.0),
            confidence: 0.9,
            frame_id: 42,
        };
        repo.append_trace(id, std::slice::from_ref(&sample))
            .unwrap();
        repo.end_session(id, None).unwrap();
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("match.json");
        export_session(&repo, id, &path).unwrap();

        let imported = import_session(&db, &path).unwrap();
        assert_ne!(imported, id);
        let original = repo.get_session(id).unwrap().unwrap();
        let copy = repo.get_session(imported).unwrap().unwrap();
        assert_eq!(
            (copy.started_at, copy.ended_at),
            (original.started_at, original.ended_at)
        );
        assert_eq!(copy.name, "Match");
        assert_eq!(copy.notes, "windy");
        assert_eq!(copy.target_profile, "air-rifle");
        assert_eq!(copy.category, "match");
        assert_eq!(copy.pre_shot_ms, 1000);
        assert_eq!(copy.shot_diameter_mm, 5.6);
        assert_eq!(copy.position, "kneeling");
        assert_eq!(copy.shots_per_series, 5);
        let shot = &repo.list_shots(imported).unwrap()[0];
        assert_eq!(shot.score, "X,\"quoted\"\nscore");
        assert_eq!(shot.x_mm, None);
        assert_eq!(shot.ts, 2.5);
        assert_eq!(repo.load_trace(imported, None, None).unwrap(), vec![sample]);
    }

    #[test]
    fn invalid_files_create_no_session() {
        let db = db();
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("session.json");
        let valid = |edit: &dyn Fn(&mut serde_json::Value)| {
            let mut value = serde_json::json!({
                "format": FORMAT, "version": VERSION,
                "session": {
                    "name": "", "startedAt": "2026-01-02 03:04:05.000000", "endedAt": null,
                    "notes": "", "targetProfile": "default", "category": "practice",
                    "appVersion": "", "preShotMs": 1, "postShotMs": 1, "releaseWindowMs": 1,
                    "shotRefractoryMs": 1, "shotDiameterMm": 4.5, "position": "standing",
                    "shotsPerSeries": 10
                },
                "shots": [], "trace": []
            });
            edit(&mut value);
            std::fs::write(&path, value.to_string()).unwrap();
            import_session(&db, &path)
        };
        let unfinished = valid(&|_| {}).unwrap();
        assert_eq!(
            SessionRepository::new(&db)
                .get_session(unfinished)
                .unwrap()
                .unwrap()
                .ended_at,
            None
        );
        assert!(valid(&|v| v["format"] = "other".into()).is_err());
        assert!(valid(&|v| v["version"] = 99.into()).is_err());
        assert!(valid(&|v| v["session"]["category"] = "bogus".into()).is_err());
        assert!(valid(&|v| v["session"]["startedAt"] = "yesterday".into()).is_err());
        assert!(valid(&|v| v["shots"] = "nope".into()).is_err());
        assert!(valid(&|v| v["session"]["preShotMs"] = (-1).into()).is_err());
        assert!(valid(&|v| v["session"]["shotsPerSeries"] = 0.into()).is_err());
        assert!(valid(&|v| v["session"]["shotDiameterMm"] = 0.into()).is_err());
        assert!(valid(&|v| v["session"]["name"] = "n".repeat(121).into()).is_err());
        assert!(
            valid(&|v| {
                v["shots"] = serde_json::json!([{
                    "seriesIndex": 0, "ts": 1.0, "xMm": null, "yMm": null,
                    "audioLevel": 0.5, "confidence": 1.0, "score": "9".repeat(17)
                }]);
            })
            .is_err()
        );
        std::fs::write(&path, "not json").unwrap();
        assert!(import_session(&db, &path).is_err());
        assert_eq!(
            SessionRepository::new(&db).list_sessions().unwrap().len(),
            1
        );
    }

    #[test]
    fn database_failure_rolls_back_the_session() {
        let db = db();
        let repo = SessionRepository::new(&db);
        db.execute_batch("CREATE TRIGGER reject_shot BEFORE INSERT ON shots BEGIN SELECT RAISE(ABORT, 'test failure'); END;").unwrap();
        let shot = NewShot {
            series_index: 0,
            ts: 1.0,
            x_mm: None,
            y_mm: None,
            audio_level: 0.5,
            confidence: 1.0,
            score: "9".into(),
        };
        let now = crate::sessions::utc_now();
        assert!(
            repo.import_session(&NewSession::default(), &[shot], &[], now, None)
                .is_err()
        );
        assert!(repo.list_sessions().unwrap().is_empty());
    }
}
