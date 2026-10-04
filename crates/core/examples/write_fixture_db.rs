//! Writes a small sessions database through `SessionRepository` and prints a
//! JSON summary of what it stored. `scripts/check_rust_db.py` reads the file
//! back through the Python repository and compares it with that summary.
//!
//! Usage: `write_fixture_db <database path> [<csv export directory>]`

use std::path::Path;
use std::process::ExitCode;

use chrono::NaiveDate;
use serde_json::{Value, json};
use shottrainer_core::services::exporter::export_session_csv;
use shottrainer_core::sessions::{NewSession, NewShot, SessionRepository, make_engine};
use shottrainer_tracking::models::TrackingSample;

const TRACE_SAMPLES: usize = 40;
const MISSING_MM_INDEX: usize = 17;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(db_path) = args.first() else {
        eprintln!("usage: write_fixture_db <database path> [<csv export directory>]");
        return ExitCode::from(2);
    };
    match run(db_path, args.get(1).map(Path::new)) {
        Ok(summary) => {
            println!("{summary}");
            ExitCode::SUCCESS
        }
        Err(err) => {
            eprintln!("write_fixture_db failed: {err}");
            ExitCode::FAILURE
        }
    }
}

fn run(db_path: &str, csv_dir: Option<&Path>) -> Result<Value, Box<dyn std::error::Error>> {
    if Path::new(db_path).exists() {
        return Err(format!("{db_path} already exists").into());
    }
    let db = make_engine(db_path)?;
    let repo = SessionRepository::new(&db);

    let match_id = repo.create_session(&NewSession {
        name: "Match one",
        notes: "fixture, with a comma and a \"quote\"",
        target_profile: "air_rifle_10m",
        app_version: "0.0.0",
        category: "match",
    })?;
    let samples: Vec<TrackingSample> = (0..TRACE_SAMPLES)
        .map(|i| {
            let mut s =
                TrackingSample::new(100.0 + i as f64 * 0.033, 320.0 + i as f64 * 0.5, 240.0);
            s.confidence = 0.9;
            s.frame_id = i as i64;
            if i != MISSING_MM_INDEX {
                s.x_mm = Some(i as f64 * 0.25 - 5.0);
                s.y_mm = Some(2.5 - i as f64 * 0.125);
            }
            s
        })
        .collect();
    repo.append_trace(match_id, &samples)?;

    // Inserted out of timestamp order so list_shots has to sort them.
    let shot_specs: [(f64, Option<f64>, Option<f64>, &str); 3] = [
        (101.0, Some(1.5), Some(-2.25), "9.7"),
        (100.5, Some(0.0), Some(0.5), "X"),
        (101.25, None, None, ""),
    ];
    let mut shot_ids = Vec::new();
    for (ts, x_mm, y_mm, score) in shot_specs {
        shot_ids.push(repo.add_shot(
            match_id,
            &NewShot {
                ts,
                x_mm,
                y_mm,
                audio_level: 0.5,
                confidence: 0.75,
                score: score.to_string(),
            },
        )?);
    }
    let ended_at = NaiveDate::from_ymd_opt(2026, 1, 2)
        .and_then(|d| d.and_hms_micro_opt(3, 4, 5, 678_901))
        .ok_or("invalid fixed timestamp")?;
    repo.end_session(match_id, Some(ended_at))?;

    let practice_id = repo.create_session(&NewSession {
        name: "Practice one",
        ..NewSession::default()
    })?;

    if let Some(dir) = csv_dir {
        export_session_csv(&repo, match_id, dir)?;
        export_session_csv(&repo, practice_id, dir)?;
    }

    let ordered: Vec<i64> = repo.list_shots(match_id)?.iter().map(|s| s.id).collect();
    let total_sessions = repo.list_sessions()?.len();
    Ok(json!({
        "sessions": [
            {
                "id": match_id,
                "name": "Match one",
                "category": "match",
                "ended_at": "2026-01-02 03:04:05.678901",
                "trace_count": TRACE_SAMPLES,
                "missing_mm_index": MISSING_MM_INDEX,
                "shot_ids_by_insert": shot_ids,
                "shot_ids_by_time": ordered,
                "shot_scores_by_time": ["X", "9.7", ""],
                "total_score": 19.7,
            },
            {
                "id": practice_id,
                "name": "Practice one",
                "category": "practice",
                "ended_at": null,
                "trace_count": 0,
                "shot_ids_by_time": [],
                "total_score": 0.0,
            },
        ],
        "session_total": total_sessions,
    }))
}
