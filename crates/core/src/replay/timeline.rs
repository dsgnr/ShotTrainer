//! Lookup of the trace sample nearest a timestamp.

use crate::bisect::bisect_left;
use shottrainer_tracking::models::TrackingSample;

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
    fn index_of_nearest_matches_the_golden_cases_and_prefers_the_earlier_tie() {
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
}
