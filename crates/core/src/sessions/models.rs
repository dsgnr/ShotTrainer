//! Session and shot records, plus the datetime text format used on disk.

use chrono::NaiveDateTime;

pub const SCHEMA_VERSION: i64 = 3;

/// Allowed values for `Session::category`. The strings are stored verbatim
/// in the database, so they stay stable across versions.
pub const SESSION_CATEGORIES: [&str; 3] = ["practice", "sighter", "match"];
pub const DEFAULT_SESSION_CATEGORY: &str = "practice";

/// The text SQLAlchemy writes for a naive `DateTime` on SQLite. The six
/// fractional digits are always present, even when they are zero.
pub const DATETIME_FORMAT: &str = "%Y-%m-%d %H:%M:%S%.6f";

/// Naive UTC time, matching the tz-naive `DateTime` columns.
pub fn utc_now() -> NaiveDateTime {
    chrono::Utc::now().naive_utc()
}

pub fn format_datetime(dt: &NaiveDateTime) -> String {
    dt.format(DATETIME_FORMAT).to_string()
}

/// Parses the stored text with or without fractional seconds. A `T`
/// separator is accepted as well as a space.
pub fn parse_datetime(text: &str) -> Option<NaiveDateTime> {
    const FORMATS: [&str; 4] = [
        "%Y-%m-%d %H:%M:%S%.f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%.f",
        "%Y-%m-%dT%H:%M:%S",
    ];
    let text = text.trim();
    FORMATS
        .iter()
        .find_map(|format| NaiveDateTime::parse_from_str(text, format).ok())
}

#[derive(Debug, Clone, PartialEq)]
pub struct Session {
    pub id: i64,
    pub name: String,
    pub started_at: NaiveDateTime,
    pub ended_at: Option<NaiveDateTime>,
    pub notes: String,
    pub target_profile: String,
    pub category: String,
    pub app_version: String,
    pub schema_version: i64,
    pub shots: Vec<Shot>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Shot {
    pub id: i64,
    pub session_id: i64,
    pub ts: f64,
    pub x_mm: Option<f64>,
    pub y_mm: Option<f64>,
    pub audio_level: f64,
    pub confidence: f64,
    pub score: String,
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::NaiveDate;

    fn dt(micro: u32) -> NaiveDateTime {
        NaiveDate::from_ymd_opt(2026, 1, 2)
            .unwrap()
            .and_hms_micro_opt(3, 4, 5, micro)
            .unwrap()
    }

    #[test]
    fn format_matches_sqlalchemy_text() {
        assert_eq!(format_datetime(&dt(678_901)), "2026-01-02 03:04:05.678901");
        assert_eq!(format_datetime(&dt(0)), "2026-01-02 03:04:05.000000");
        assert_eq!(format_datetime(&dt(10)), "2026-01-02 03:04:05.000010");
    }

    #[test]
    fn parse_accepts_stored_forms() {
        assert_eq!(
            parse_datetime("2026-01-02 03:04:05.678901"),
            Some(dt(678_901))
        );
        assert_eq!(parse_datetime("2026-01-02 03:04:05.000000"), Some(dt(0)));
        assert_eq!(parse_datetime("2026-01-02 03:04:05"), Some(dt(0)));
        assert_eq!(parse_datetime("2026-01-02 03:04:05.5"), Some(dt(500_000)));
        assert_eq!(
            parse_datetime("2026-01-02T03:04:05.678901"),
            Some(dt(678_901))
        );
    }

    #[test]
    fn parse_rejects_garbage() {
        assert_eq!(parse_datetime(""), None);
        assert_eq!(parse_datetime("yesterday"), None);
        assert_eq!(parse_datetime("2026-13-02 03:04:05"), None);
    }

    #[test]
    fn round_trip() {
        let value = dt(123_456);
        assert_eq!(parse_datetime(&format_datetime(&value)), Some(value));
    }

    #[test]
    fn utc_now_has_no_offset_drift() {
        let now = utc_now();
        assert_eq!(parse_datetime(&format_datetime(&now)), Some(now));
    }
}
