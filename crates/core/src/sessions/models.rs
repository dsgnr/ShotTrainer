//! Session and shot records, plus the datetime text format used on disk.

use chrono::{NaiveDateTime, SubsecRound};

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
    truncate_to_micros(chrono::Utc::now().naive_utc())
}

/// Drops sub-microsecond precision, which the stored text cannot hold.
/// Every datetime written to the database goes through this first so it
/// reads back equal.
pub fn truncate_to_micros(dt: NaiveDateTime) -> NaiveDateTime {
    dt.trunc_subsecs(6)
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
        .or_else(|| {
            chrono::NaiveDate::parse_from_str(text, "%Y-%m-%d")
                .ok()
                .and_then(|date| date.and_hms_opt(0, 0, 0))
        })
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
    fn parse_accepts_date_only_as_midnight() {
        assert_eq!(
            parse_datetime("2026-01-02"),
            NaiveDate::from_ymd_opt(2026, 1, 2)
                .unwrap()
                .and_hms_opt(0, 0, 0)
        );
    }

    #[test]
    fn truncation_drops_sub_microsecond_digits() {
        let nanos = NaiveDate::from_ymd_opt(2026, 1, 2)
            .unwrap()
            .and_hms_nano_opt(3, 4, 5, 123_456_789)
            .unwrap();
        assert_eq!(
            format_datetime(&truncate_to_micros(nanos)),
            "2026-01-02 03:04:05.123456"
        );
        assert_eq!(
            parse_datetime(&format_datetime(&truncate_to_micros(nanos))),
            Some(truncate_to_micros(nanos))
        );
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
