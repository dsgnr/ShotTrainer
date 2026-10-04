//! Exports a saved session to CSV.
//!
//! The files are written by hand to match Python's `csv.writer` output byte
//! for byte. Rows end in `\r\n` and a field is quoted only when it contains a
//! comma, a quote or a line break, with embedded quotes doubled.

use std::path::{Path, PathBuf};

use crate::sessions::{DatabaseError, SessionRepository};

#[derive(Debug, thiserror::Error)]
pub enum ExportError {
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Database(#[from] DatabaseError),
}

/// Writes `session_<id>_shots.csv` and `session_<id>_trace.csv` into
/// `target_dir`, creating it when missing, and returns both paths.
pub fn export_session_csv(
    repo: &SessionRepository,
    session_id: i64,
    target_dir: &Path,
) -> Result<Vec<PathBuf>, ExportError> {
    std::fs::create_dir_all(target_dir)?;

    let mut shots = String::new();
    write_row(
        &mut shots,
        &[
            "index",
            "timestamp",
            "x_mm",
            "y_mm",
            "audio_level",
            "confidence",
            "score",
        ],
    );
    for (i, shot) in repo.list_shots(session_id)?.iter().enumerate() {
        write_row(
            &mut shots,
            &[
                &i.to_string(),
                &fixed(shot.ts, 6),
                &optional(shot.x_mm, 3),
                &optional(shot.y_mm, 3),
                &fixed(shot.audio_level, 4),
                &fixed(shot.confidence, 4),
                &shot.score,
            ],
        );
    }
    let shots_path = target_dir.join(format!("session_{session_id}_shots.csv"));
    std::fs::write(&shots_path, shots)?;

    let mut trace = String::new();
    write_row(
        &mut trace,
        &[
            "timestamp",
            "x_px",
            "y_px",
            "x_mm",
            "y_mm",
            "confidence",
            "frame_id",
        ],
    );
    for s in repo.load_trace(session_id, None, None)? {
        write_row(
            &mut trace,
            &[
                &fixed(s.timestamp, 6),
                &fixed(s.x_px, 3),
                &fixed(s.y_px, 3),
                &optional(s.x_mm, 3),
                &optional(s.y_mm, 3),
                &fixed(s.confidence, 4),
                &s.frame_id.to_string(),
            ],
        );
    }
    let trace_path = target_dir.join(format!("session_{session_id}_trace.csv"));
    std::fs::write(&trace_path, trace)?;

    Ok(vec![shots_path, trace_path])
}

/// Python spells the non-finite values `nan`, `inf` and `-inf`.
fn fixed(value: f64, places: usize) -> String {
    if value.is_nan() {
        "nan".to_string()
    } else {
        format!("{value:.places$}")
    }
}

fn optional(value: Option<f64>, places: usize) -> String {
    value.map_or_else(String::new, |v| fixed(v, places))
}

fn write_row(out: &mut String, fields: &[&str]) {
    for (i, field) in fields.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        if field.contains([',', '"', '\r', '\n']) {
            out.push('"');
            out.push_str(&field.replace('"', "\"\""));
            out.push('"');
        } else {
            out.push_str(field);
        }
    }
    out.push_str("\r\n");
}
