//! Readers for single JSON values that follow `matches_setting_type` in the
//! Python code. Booleans are never numbers and strings are never coerced.

use std::path::Path;

use serde_json::{Map, Value};

use crate::json_write::python_float_repr;

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

/// A finite JSON number, integer or float. Python's `float()` of a JSON number
/// accepts all of them except booleans.
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
    match serde_json::from_str::<Value>(&replace_non_finite(&text)) {
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

/// Python's whitespace for `float()` and `int()` also covers the ASCII
/// separators `\x1c` to `\x1f`.
fn trim_python_space(text: &str) -> &str {
    text.trim_matches(|c: char| c.is_whitespace() || ('\x1c'..='\x1f').contains(&c))
}

/// Consumes `digit (_? digit)*` from the front of `text` and returns the digits
/// without underscores plus the rest.
fn take_digits(text: &str) -> Option<(String, &str)> {
    let bytes = text.as_bytes();
    let mut digits = String::new();
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'0'..=b'9' => digits.push(char::from(bytes[i])),
            b'_' if !digits.is_empty() && bytes.get(i + 1).is_some_and(u8::is_ascii_digit) => {}
            _ => break,
        }
        i += 1;
    }
    (!digits.is_empty()).then(|| (digits, &text[i..]))
}

/// `int(text)` for a decimal string. Returns `None` where Python raises
/// `ValueError` and saturates values too large for `i128`. Non-ASCII digits,
/// which Python also accepts, are rejected.
pub(crate) fn parse_python_int(text: &str) -> Option<i128> {
    let text = trim_python_space(text);
    let (negative, body) = match text.as_bytes().first()? {
        b'-' => (true, &text[1..]),
        b'+' => (false, &text[1..]),
        _ => (false, text),
    };
    let (digits, rest) = take_digits(body)?;
    if !rest.is_empty() {
        return None;
    }
    let magnitude = digits.parse::<i128>().unwrap_or(i128::MAX);
    Some(if negative { -magnitude } else { magnitude })
}

/// `float(text)` for a decimal string, finite results only. `nan`, `inf` and
/// `infinity` are Python-valid but non-finite, so they give `None` here as does
/// any overflow. Non-ASCII digits, which Python also accepts, are rejected.
pub(crate) fn parse_python_finite_float(text: &str) -> Option<f64> {
    let text = trim_python_space(text);
    let body = text.strip_prefix(['-', '+']).unwrap_or(text);
    let mut clean = String::from(&text[..text.len() - body.len()]);
    let mut rest = body;
    if let Some((int_part, after)) = take_digits(rest) {
        clean.push_str(&int_part);
        rest = after;
        if let Some(after_dot) = rest.strip_prefix('.') {
            clean.push('.');
            rest = after_dot;
            if let Some((frac, after)) = take_digits(rest) {
                clean.push_str(&frac);
                rest = after;
            }
        }
    } else {
        rest = rest.strip_prefix('.')?;
        let (frac, after) = take_digits(rest)?;
        clean.push('.');
        clean.push_str(&frac);
        rest = after;
    }
    if let Some(after_e) = rest.strip_prefix(['e', 'E']) {
        clean.push('e');
        let after_e = match after_e.strip_prefix(['-', '+']) {
            Some(after_sign) => {
                clean.push_str(&after_e[..1]);
                after_sign
            }
            None => after_e,
        };
        let (exp, after) = take_digits(after_e)?;
        clean.push_str(&exp);
        rest = after;
    }
    if !rest.is_empty() {
        return None;
    }
    clean.parse::<f64>().ok().filter(|v| v.is_finite())
}

/// `str(value)` for a decoded JSON value, as Python would print it.
pub(crate) fn python_str(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        other => python_repr(other),
    }
}

fn python_repr(value: &Value) -> String {
    match value {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Number(n) => match n.as_f64() {
            Some(f) if n.is_f64() && f.is_finite() => python_float_repr(f),
            _ => n.to_string(),
        },
        Value::String(s) => python_string_repr(s),
        Value::Array(items) => {
            let parts: Vec<String> = items.iter().map(python_repr).collect();
            format!("[{}]", parts.join(", "))
        }
        Value::Object(map) => {
            let parts: Vec<String> = map
                .iter()
                .map(|(k, v)| format!("{}: {}", python_string_repr(k), python_repr(v)))
                .collect();
            format!("{{{}}}", parts.join(", "))
        }
    }
}

/// `repr(str)`. Printable characters are judged by `char::is_control`, which is
/// close to Python's `isprintable` but not identical for exotic code points.
fn python_string_repr(text: &str) -> String {
    let quote = if text.contains('\'') && !text.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::from(quote);
    for c in text.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if c.is_control() => {
                let code = u32::from(c);
                if code <= 0xff {
                    out.push_str(&format!("\\x{code:02x}"));
                } else if code <= 0xffff {
                    out.push_str(&format!("\\u{code:04x}"));
                } else {
                    out.push_str(&format!("\\U{code:08x}"));
                }
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// Rewrites tokens serde_json and Python read differently. Replaces `NaN`,
/// `Infinity`, `-Infinity` and numbers that overflow to infinity with `[]`,
/// which no preference accepts, so the rest of the document still parses.
/// Python's `json` reads these tokens and writes them for non-finite floats.
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
