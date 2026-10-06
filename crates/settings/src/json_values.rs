//! Readers for single JSON values. Booleans are never numbers and strings are
//! never coerced.

use std::path::Path;

use serde_json::{Map, Value};

pub(crate) fn read_bool(value: &Value) -> Option<bool> {
    value.as_bool()
}

pub(crate) fn read_string(value: &Value) -> Option<String> {
    value.as_str().map(str::to_owned)
}

/// A JSON integer (not `1.0`) within the signed 32-bit range.
pub(crate) fn read_i32(value: &Value) -> Option<i32> {
    i32::try_from(value.as_i64()?).ok()
}

pub(crate) fn read_i32_in(value: &Value, low: i32, high: i32) -> Option<i32> {
    read_i32(value).filter(|v| (low..=high).contains(v))
}

/// A finite JSON number, integer or float, within `low..=high`.
pub(crate) fn read_f64_in(value: &Value, low: f64, high: f64) -> Option<f64> {
    if !value.is_number() {
        return None;
    }
    let v = value.as_f64()?;
    (v.is_finite() && low <= v && v <= high).then_some(v)
}

/// A finite JSON number, integer or float.
pub(crate) fn read_finite_f64(value: &Value) -> Option<f64> {
    read_f64_in(value, f64::MIN, f64::MAX)
}

pub(crate) fn read_i32_choice(value: &Value, choices: &[i32]) -> Option<i32> {
    read_i32(value).filter(|v| choices.contains(v))
}

/// Reads `path` as a JSON object, giving `None` with a warning when the file is
/// missing, unreadable, not UTF-8, not JSON or not an object.
pub(crate) fn read_json_object(path: &Path, what: &str) -> Option<Map<String, Value>> {
    if !path.exists() {
        return None;
    }
    let text = match std::fs::read_to_string(path) {
        Ok(text) => text,
        Err(err) => {
            log::warn!("Could not read {}: {err}. Using defaults", path.display());
            return None;
        }
    };
    match serde_json::from_str::<Value>(&text) {
        Ok(Value::Object(map)) => Some(map),
        Ok(_) => {
            log::warn!("{what} file must contain a JSON object. Using defaults");
            None
        }
        Err(err) => {
            log::warn!("Could not read {}: {err}. Using defaults", path.display());
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn booleans_are_not_integers_or_floats() {
        assert_eq!(read_i32(&json!(true)), None);
        assert_eq!(read_f64_in(&json!(true), 0.0, 2.0), None);
        assert_eq!(read_bool(&json!(1)), None);
    }

    #[test]
    fn integers_reject_floats_and_out_of_range_values() {
        assert_eq!(read_i32(&json!(1.0)), None);
        assert_eq!(read_i32(&json!(1u64 << 31)), None);
        assert_eq!(read_i32(&json!(i32::MIN)), Some(i32::MIN));
        assert_eq!(read_i32_in(&json!(5), 0, 4), None);
    }

    #[test]
    fn floats_accept_integers_inside_the_range() {
        assert_eq!(read_f64_in(&json!(2), 0.1, 10.0), Some(2.0));
        assert_eq!(read_f64_in(&json!(10.5), 0.1, 10.0), None);
        assert_eq!(read_f64_in(&json!("2"), 0.1, 10.0), None);
    }
}
