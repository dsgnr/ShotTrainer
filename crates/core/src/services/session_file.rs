//! The single-file session format used for export and import.

use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "shottrainer-session";
pub const VERSION: u32 = 1;

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionFile {
    pub format: String,
    pub version: u32,
    pub session: SessionSettings,
    pub shots: Vec<ShotRecord>,
    pub trace: Vec<TraceRecord>,
}

/// Datetimes use the stored text format of `sessions::format_datetime`.
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionSettings {
    pub name: String,
    pub started_at: String,
    pub ended_at: Option<String>,
    pub notes: String,
    pub target_profile: String,
    pub category: String,
    pub app_version: String,
    pub pre_shot_ms: i32,
    pub post_shot_ms: i32,
    pub release_window_ms: i32,
    pub shot_refractory_ms: i32,
    pub shot_diameter_mm: f64,
    pub position: String,
    pub shots_per_series: i32,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ShotRecord {
    pub series_index: i32,
    pub ts: f64,
    pub x_mm: Option<f64>,
    pub y_mm: Option<f64>,
    pub audio_level: f64,
    pub confidence: f64,
    pub score: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TraceRecord {
    pub timestamp: f64,
    pub x_px: f64,
    pub y_px: f64,
    pub x_mm: Option<f64>,
    pub y_mm: Option<f64>,
    pub confidence: f64,
    pub frame_id: i64,
}
