//! Helpers for tests that compare against fixtures generated from the Python code.
use std::path::PathBuf;

const TOLERANCE: f64 = 1e-9;

pub fn golden_path(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/golden")
        .join(format!("{name}.json"))
}

pub fn load_golden(name: &str) -> serde_json::Value {
    let path = golden_path(name);
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("cannot read golden fixture {path:?}: {e}"));
    serde_json::from_str(&text).unwrap_or_else(|e| panic!("bad golden fixture {path:?}: {e}"))
}

pub fn assert_close(actual: f64, expected: f64, context: &str) {
    assert!(
        (actual - expected).abs() <= TOLERANCE,
        "{context}: expected {expected}, got {actual}"
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn golden_path_points_into_testdata() {
        let p = golden_path("scoring");
        assert!(p.ends_with("testdata/golden/scoring.json"), "{p:?}");
    }

    #[test]
    fn assert_close_accepts_values_within_tolerance() {
        assert_close(1.0, 1.0 + 1e-12, "tiny difference");
    }

    #[test]
    #[should_panic(expected = "mismatch")]
    fn assert_close_rejects_values_outside_tolerance() {
        assert_close(1.0, 1.1, "mismatch");
    }
}
