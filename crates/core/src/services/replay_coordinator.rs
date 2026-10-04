//! Loads a saved shot window from the database for the replay view.

use shottrainer_tracking::models::TrackingSample;

use crate::replay::timeline::index_of_nearest;
use crate::sessions::{DatabaseError, SessionRepository};

/// Default duration of the release window, the last quarter-second before
/// the trigger breaks.
pub const DEFAULT_RELEASE_WINDOW_MS: i64 = 250;

/// Trace samples around a shot with the release boundaries.
///
/// Samples without both millimetre coordinates are omitted so every index
/// refers to the points the player and target view display. `split_index` is
/// the sample nearest the shot timestamp and `release_index` is where the
/// release window starts.
#[derive(Debug, Clone, PartialEq)]
pub struct ShotWindow {
    pub samples: Vec<TrackingSample>,
    pub split_index: Option<usize>,
    pub release_index: Option<usize>,
}

/// `release_index` is `None` when no sample falls between the release
/// threshold and the shot timestamp.
pub fn shot_window(
    repo: &SessionRepository,
    session_id: i64,
    shot_ts: f64,
    pre_ms: i64,
    post_ms: i64,
    release_ms: i64,
) -> Result<ShotWindow, DatabaseError> {
    let start = shot_ts - pre_ms as f64 / 1000.0;
    let end = shot_ts + post_ms as f64 / 1000.0;
    let samples: Vec<TrackingSample> = repo
        .load_trace(session_id, Some(start), Some(end))?
        .into_iter()
        .filter(|s| s.x_mm.is_some() && s.y_mm.is_some())
        .collect();
    let split_index = index_of_nearest(&samples, shot_ts);
    let threshold = shot_ts - release_ms as f64 / 1000.0;
    let release_index = samples
        .iter()
        .position(|s| threshold <= s.timestamp && s.timestamp <= shot_ts);
    Ok(ShotWindow {
        samples,
        split_index,
        release_index,
    })
}
