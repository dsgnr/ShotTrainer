//! Helpers for slicing a trace around a shot timestamp.

use crate::bisect::{bisect_left, bisect_right};
use shottrainer_tracking::models::TrackingSample;

/// Returns the samples within `[centre - pre, centre + post]`.
///
/// `samples` must be sorted by timestamp. A window whose start lies after its
/// end, which a negative `pre_ms` or `post_ms` can produce, yields no samples.
pub fn slice_window(
    samples: &[TrackingSample],
    centre_ts: f64,
    pre_ms: i64,
    post_ms: i64,
) -> Vec<TrackingSample> {
    if samples.is_empty() {
        return Vec::new();
    }
    let start = centre_ts - pre_ms as f64 / 1000.0;
    let end = centre_ts + post_ms as f64 / 1000.0;
    let lo = bisect_left(samples.len(), |i| samples[i].timestamp, start);
    let hi = bisect_right(samples.len(), |i| samples[i].timestamp, end);
    if lo >= hi {
        return Vec::new();
    }
    samples[lo..hi].to_vec()
}

/// Returns the index of the sample closest to `ts`, preferring the earlier
/// sample when `ts` is exactly halfway between two.
pub fn index_of_nearest(samples: &[TrackingSample], ts: f64) -> Option<usize> {
    if samples.is_empty() {
        return None;
    }
    let i = bisect_left(samples.len(), |i| samples[i].timestamp, ts);
    if i == 0 {
        return Some(0);
    }
    if i >= samples.len() {
        return Some(samples.len() - 1);
    }
    let before = samples[i - 1].timestamp;
    let after = samples[i].timestamp;
    Some(if (after - ts).abs() < (ts - before).abs() {
        i
    } else {
        i - 1
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::trace_fixture::*;

    #[test]
    fn slice_window_matches_python() {
        let mut checked = 0;
        for case in cases() {
            let snapshot = samples(&case["snapshot"]);
            for q in case["slices"].as_array().unwrap() {
                let got = slice_window(
                    &snapshot,
                    number(&q["centre"]),
                    q["pre_ms"].as_i64().unwrap(),
                    q["post_ms"].as_i64().unwrap(),
                );
                assert_refs(&got, &q["result"], &format!("{} {q}", case["name"]));
                checked += 1;
            }
        }
        assert!(checked > 1000);
    }

    #[test]
    fn index_of_nearest_matches_python_and_prefers_the_earlier_tie() {
        let mut checked = 0;
        for case in cases() {
            let snapshot = samples(&case["snapshot"]);
            for q in case["timeline_nearest"].as_array().unwrap() {
                let got = index_of_nearest(&snapshot, number(&q["query"]));
                assert_eq!(
                    got.map(|i| i as i64),
                    q["index"].as_i64(),
                    "{} {q}",
                    case["name"]
                );
                checked += 1;
            }
        }
        assert!(checked > 100);
        let even = [0.0, 1.0].map(|t| TrackingSample::new(t, 0.0, 0.0));
        assert_eq!(index_of_nearest(&even, 0.5), Some(0));
    }

    #[test]
    fn reversed_window_is_empty() {
        let s: Vec<_> = [0.0, 1.0, 2.0]
            .map(|t| TrackingSample::new(t, 0.0, 0.0))
            .to_vec();
        assert!(slice_window(&s, 1.0, -1000, -1000).is_empty());
    }
}
