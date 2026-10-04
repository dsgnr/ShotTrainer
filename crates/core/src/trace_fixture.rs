//! Loader for the `trace` golden fixture shared by the trace tests.

use serde_json::Value;
use shottrainer_tracking::models::TrackingSample;

pub fn cases() -> Vec<Value> {
    let golden = testkit::load_golden("trace");
    let cases = golden["cases"].as_array().expect("cases").clone();
    assert_eq!(cases.len(), 6, "fixture must keep all six sample sets");
    cases
}

pub fn number(value: &Value) -> f64 {
    match value {
        Value::String(s) => match s.as_str() {
            "nan" => f64::NAN,
            "inf" => f64::INFINITY,
            "-inf" => f64::NEG_INFINITY,
            other => panic!("unexpected number string {other}"),
        },
        other => other.as_f64().expect("number"),
    }
}

pub fn sample(value: &Value) -> TrackingSample {
    let mut s = TrackingSample::new(number(&value["timestamp"]), 0.0, 0.0);
    s.frame_id = value["frame_id"].as_i64().expect("frame_id");
    s
}

pub fn samples(value: &Value) -> Vec<TrackingSample> {
    value
        .as_array()
        .expect("array")
        .iter()
        .map(sample)
        .collect()
}

/// Asserts the samples match the fixture list by frame id and timestamp bits.
pub fn assert_refs(actual: &[TrackingSample], expected: &Value, context: &str) {
    let expected = expected.as_array().expect("array");
    assert_eq!(actual.len(), expected.len(), "{context}: length");
    for (a, e) in actual.iter().zip(expected) {
        assert_eq!(a.frame_id, e["frame_id"].as_i64().unwrap(), "{context}");
        assert_eq!(
            a.timestamp.to_bits(),
            e["timestamp"].as_f64().unwrap().to_bits(),
            "{context}"
        );
    }
}

pub fn assert_ref(actual: Option<&TrackingSample>, expected: &Value, context: &str) {
    match (actual, expected) {
        (None, Value::Null) => {}
        (Some(a), e) if !e.is_null() => {
            assert_eq!(a.frame_id, e["frame_id"].as_i64().unwrap(), "{context}");
            assert_eq!(
                a.timestamp.to_bits(),
                e["timestamp"].as_f64().unwrap().to_bits(),
                "{context}"
            );
        }
        (a, e) => panic!("{context}: got {a:?}, expected {e}"),
    }
}
