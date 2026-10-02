//! Imports the shot and optional trace files written by the CSV exporter.

use std::path::Path;

use shottrainer_tracking::models::TrackingSample;

use crate::sessions::{DatabaseError, Db, NewSession, NewShot, SessionRepository};

#[derive(Debug, thiserror::Error)]
pub enum ImportError {
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Database(#[from] DatabaseError),
    #[error("Invalid CSV: {0}")]
    Invalid(String),
}

pub fn import_session_csv(db: &Db, path: &Path) -> Result<i64, ImportError> {
    let stem = path
        .file_stem()
        .and_then(|s| s.to_str())
        .and_then(|s| s.strip_suffix("_shots"))
        .ok_or_else(|| ImportError::Invalid("select a *_shots.csv file".into()))?;
    let rows = read_rows(
        path,
        &[
            "index",
            "timestamp",
            "x_mm",
            "y_mm",
            "audio_level",
            "confidence",
            "score",
        ],
    )?;
    let mut shots = Vec::new();
    for (position, row) in rows.iter().enumerate() {
        let index = integer(&row[0])?;
        if index != position as i64 {
            return Err(ImportError::Invalid(
                "shot indices must be consecutive from zero".into(),
            ));
        }
        shots.push(NewShot {
            series_index: i32::try_from(index / 10)
                .map_err(|_| ImportError::Invalid("too many shots".into()))?,
            ts: number(&row[1])?,
            x_mm: optional(&row[2])?,
            y_mm: optional(&row[3])?,
            audio_level: number(&row[4])?,
            confidence: number(&row[5])?,
            score: row[6].clone(),
        });
    }
    let trace_path = path.with_file_name(format!("{stem}_trace.csv"));
    let trace_rows = match read_rows(
        &trace_path,
        &[
            "timestamp",
            "x_px",
            "y_px",
            "x_mm",
            "y_mm",
            "confidence",
            "frame_id",
        ],
    ) {
        Err(ImportError::Io(error)) if error.kind() == std::io::ErrorKind::NotFound => Vec::new(),
        result => result?,
    };
    let mut trace = Vec::new();
    for row in trace_rows {
        trace.push(TrackingSample {
            timestamp: number(&row[0])?,
            x_px: number(&row[1])?,
            y_px: number(&row[2])?,
            x_mm: optional(&row[3])?,
            y_mm: optional(&row[4])?,
            confidence: number(&row[5])?,
            frame_id: integer(&row[6])?,
        });
    }
    let repo = SessionRepository::new(db);
    Ok(repo.import_session(
        &NewSession {
            name: &format!("Imported {stem}"),
            app_version: env!("CARGO_PKG_VERSION"),
            ..NewSession::default()
        },
        &shots,
        &trace,
    )?)
}

fn number(value: &str) -> Result<f64, ImportError> {
    value
        .parse::<f64>()
        .ok()
        .filter(|n| n.is_finite())
        .ok_or_else(|| ImportError::Invalid(format!("expected a finite number, got {value:?}")))
}

fn optional(value: &str) -> Result<Option<f64>, ImportError> {
    if value.is_empty() {
        Ok(None)
    } else {
        number(value).map(Some)
    }
}

fn integer(value: &str) -> Result<i64, ImportError> {
    value
        .parse()
        .map_err(|_| ImportError::Invalid(format!("expected an integer, got {value:?}")))
}

fn read_rows(path: &Path, header: &[&str]) -> Result<Vec<Vec<String>>, ImportError> {
    let text = std::fs::read_to_string(path)?;
    let mut chars = text.trim_start_matches('\u{feff}').chars().peekable();
    let mut rows = Vec::new();
    let mut row = Vec::new();
    let mut field = String::new();
    let mut quoted = false;
    let mut closed = false;
    while let Some(c) = chars.next() {
        if quoted {
            if c == '"' {
                if chars.peek() == Some(&'"') {
                    chars.next();
                    field.push('"');
                } else {
                    quoted = false;
                    closed = true;
                }
            } else {
                field.push(c);
            }
        } else {
            match c {
                '"' if field.is_empty() && !closed => quoted = true,
                ',' => {
                    row.push(std::mem::take(&mut field));
                    closed = false;
                }
                '\r' | '\n' => {
                    if c == '\r' && chars.peek() == Some(&'\n') {
                        chars.next();
                    }
                    row.push(std::mem::take(&mut field));
                    rows.push(std::mem::take(&mut row));
                    closed = false;
                }
                '"' => return Err(ImportError::Invalid("unexpected quote".into())),
                _ if closed => return Err(ImportError::Invalid("text after closing quote".into())),
                _ => field.push(c),
            }
        }
    }
    if quoted {
        return Err(ImportError::Invalid("unterminated quoted field".into()));
    }
    if !field.is_empty() || !row.is_empty() || closed {
        row.push(field);
        rows.push(row);
    }
    if rows
        .first()
        .map(|r| r.iter().map(String::as_str).collect::<Vec<_>>())
        != Some(header.to_vec())
    {
        return Err(ImportError::Invalid("unexpected column headers".into()));
    }
    rows.remove(0);
    if rows.iter().any(|r| r.len() != header.len()) {
        return Err(ImportError::Invalid("incorrect column count".into()));
    }
    Ok(rows)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::services::exporter::export_session_csv;
    use crate::sessions::{init_database, make_engine};

    fn db() -> Db {
        let db = make_engine(":memory:").unwrap();
        init_database(&db).unwrap();
        db
    }

    #[test]
    fn exported_shots_and_trace_round_trip() {
        let db = db();
        let repo = SessionRepository::new(&db);
        let id = repo.create_session(&NewSession::default()).unwrap();
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
        let dir = tempfile::tempdir().unwrap();
        let files = export_session_csv(&repo, id, dir.path()).unwrap();
        let imported = import_session_csv(&db, &files[0]).unwrap();
        let shot = &repo.list_shots(imported).unwrap()[0];
        assert_eq!(shot.score, "X,\"quoted\"\nscore");
        assert_eq!(shot.x_mm, None);
        assert_eq!(shot.ts, 2.5);
        assert_eq!(repo.load_trace(imported, None, None).unwrap(), vec![sample]);
        assert!(
            repo.get_session(imported)
                .unwrap()
                .unwrap()
                .ended_at
                .is_some()
        );
    }

    #[test]
    fn missing_trace_is_allowed_and_bad_rows_create_no_session() {
        let db = db();
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("session_1_shots.csv");
        let header = "index,timestamp,x_mm,y_mm,audio_level,confidence,score\n";
        std::fs::write(&path, format!("{header}0,1,,,0.5,1,9\n")).unwrap();
        import_session_csv(&db, &path).unwrap();
        for row in [
            "0,NaN,,,0.5,1,9",
            "0,1,,,0.5,1",
            "1,1,,,0.5,1,9",
            "0,1,,,0.5,1,\"unclosed",
        ] {
            std::fs::write(&path, format!("{header}{row}\n")).unwrap();
            assert!(import_session_csv(&db, &path).is_err());
            assert_eq!(
                SessionRepository::new(&db).list_sessions().unwrap().len(),
                1
            );
        }
        std::fs::write(&path, header).unwrap();
        std::fs::write(dir.path().join("session_1_trace.csv"), "wrong headers\n").unwrap();
        assert!(import_session_csv(&db, &path).is_err());
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
        assert!(
            repo.import_session(&NewSession::default(), &[shot], &[])
                .is_err()
        );
        assert!(repo.list_sessions().unwrap().is_empty());
    }
}
