//! Readers for single JSON values that follow `matches_setting_type` in the
//! Python code. Booleans are never numbers and strings are never coerced.

use serde_json::Value;

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

pub(crate) fn read_i32_choice(value: &Value, choices: &[i32]) -> Option<i32> {
    read_i32(value).filter(|v| choices.contains(v))
}

/// Rewrites tokens serde_json and Python read differently. Replaces `NaN`, `Infinity`, `-Infinity` and numbers that overflow to
/// infinity with `[]`, which no preference accepts, so the rest of the
/// document still parses. Python's `json` reads these tokens and writes them
/// for non-finite floats.
pub(crate) fn replace_non_finite(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len());
    let mut i = 0;
    let starts = |at: usize, word: &str| {
        word.chars()
            .enumerate()
            .all(|(k, c)| chars.get(at + k) == Some(&c))
    };
    while i < chars.len() {
        let c = chars[i];
        if c == '"' {
            out.push(c);
            i += 1;
            while i < chars.len() {
                out.push(chars[i]);
                i += 1;
                if chars[i - 1] == '\\' && i < chars.len() {
                    out.push(chars[i]);
                    i += 1;
                } else if chars[i - 1] == '"' {
                    break;
                }
            }
        } else if starts(i, "NaN") {
            out.push_str("[]");
            i += 3;
        } else if starts(i, "Infinity") {
            out.push_str("[]");
            i += 8;
        } else if c == '-' && starts(i + 1, "Infinity") {
            out.push_str("[]");
            i += 9;
        } else if c == '-' || c.is_ascii_digit() {
            let start = i;
            i += 1;
            while i < chars.len() && matches!(chars[i], '0'..='9' | '.' | 'e' | 'E' | '+' | '-') {
                i += 1;
            }
            let token: String = chars[start..i].iter().collect();
            if token.parse::<f64>().is_ok_and(f64::is_infinite) {
                out.push_str("[]");
            } else if token == "-0" {
                // serde_json reads this integer as a float, Python as 0.
                out.push('0');
            } else {
                out.push_str(&token);
            }
        } else {
            out.push(c);
            i += 1;
        }
    }
    out
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

    #[test]
    fn replaces_tokens_outside_strings_only() {
        let text = r#"{"a": NaN, "b": -Infinity, "c": "NaN \" Infinity", "d": 1e999, "e": 2.5, "f": -0, "g": -0.5}"#;
        let fixed = replace_non_finite(text);
        let v: Value = serde_json::from_str(&fixed).unwrap();
        assert_eq!(v["a"], json!([]));
        assert_eq!(v["b"], json!([]));
        assert_eq!(v["c"], json!("NaN \" Infinity"));
        assert_eq!(v["d"], json!([]));
        assert_eq!(v["e"], json!(2.5));
        assert_eq!(v["f"].as_i64(), Some(0));
        assert_eq!(v["g"], json!(-0.5));
    }
}
