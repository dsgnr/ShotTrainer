//! Statistics over shot positions and trace windows.

/// Group statistics for a set of shot positions.
///
/// `extreme_spread_mm` is the largest distance between any two shots.
/// `mean_radius_mm` is the mean distance from the group centroid.
#[derive(Debug, Clone, PartialEq)]
pub struct ShotStats {
    pub count: usize,
    pub mean_x_mm: f64,
    pub mean_y_mm: f64,
    pub extreme_spread_mm: f64,
    pub mean_radius_mm: f64,
}

/// Stability numbers for a stretch of trace.
///
/// `hold_tremor_mm` is the RMS distance from the mean position and
/// `trace_length_mm` is the total path length.
#[derive(Debug, Clone, PartialEq)]
pub struct TraceStats {
    pub samples: usize,
    pub hold_tremor_mm: f64,
    pub trace_length_mm: f64,
    pub mean_x_mm: f64,
    pub mean_y_mm: f64,
}

/// Python sums floats from an integer zero, so the fold starts at `+0.0`
/// where `Iterator::sum` would start at `-0.0`.
fn sum(values: impl Iterator<Item = f64>) -> f64 {
    values.fold(0.0, |acc, v| acc + v)
}

pub fn compute_stats(positions: &[(f64, f64)]) -> ShotStats {
    if positions.is_empty() {
        return ShotStats {
            count: 0,
            mean_x_mm: 0.0,
            mean_y_mm: 0.0,
            extreme_spread_mm: 0.0,
            mean_radius_mm: 0.0,
        };
    }
    let n = positions.len() as f64;
    let cx = sum(positions.iter().map(|p| p.0)) / n;
    let cy = sum(positions.iter().map(|p| p.1)) / n;
    let mean_radius = sum(positions.iter().map(|p| (p.0 - cx).hypot(p.1 - cy))) / n;

    // A NaN distance propagates to the result, as with `np.max`.
    let mut spread = 0.0_f64;
    for a in positions {
        for b in positions {
            let d = (a.0 - b.0).hypot(a.1 - b.1);
            if d.is_nan() {
                spread = f64::NAN;
            } else if d > spread {
                spread = d;
            }
        }
    }

    ShotStats {
        count: positions.len(),
        mean_x_mm: cx,
        mean_y_mm: cy,
        extreme_spread_mm: spread,
        mean_radius_mm: mean_radius,
    }
}

pub fn compute_trace_stats(points: &[(f64, f64)]) -> TraceStats {
    if points.is_empty() {
        return TraceStats {
            samples: 0,
            hold_tremor_mm: 0.0,
            trace_length_mm: 0.0,
            mean_x_mm: 0.0,
            mean_y_mm: 0.0,
        };
    }
    let n = points.len() as f64;
    let cx = sum(points.iter().map(|p| p.0)) / n;
    let cy = sum(points.iter().map(|p| p.1)) / n;

    let mut squares = 0.0;
    let mut length = 0.0;
    let mut previous: Option<(f64, f64)> = None;
    for &(x, y) in points {
        squares += (x - cx) * (x - cx) + (y - cy) * (y - cy);
        if let Some(prev) = previous {
            length += (x - prev.0).hypot(y - prev.1);
        }
        previous = Some((x, y));
    }
    TraceStats {
        samples: points.len(),
        hold_tremor_mm: (squares / n).sqrt(),
        trace_length_mm: length,
        mean_x_mm: cx,
        mean_y_mm: cy,
    }
}

/// Fraction of samples within `radius_mm` of `centre`, or `0.0` for an empty trace.
pub fn time_inside_radius(points: &[(f64, f64)], radius_mm: f64, centre: (f64, f64)) -> f64 {
    if points.is_empty() {
        return 0.0;
    }
    let inside = points
        .iter()
        .filter(|p| (p.0 - centre.0).hypot(p.1 - centre.1) <= radius_mm)
        .count();
    inside as f64 / points.len() as f64
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;
    use testkit::{assert_close, load_golden};

    fn points(v: &serde_json::Value) -> Vec<(f64, f64)> {
        v.as_array()
            .unwrap()
            .iter()
            .map(|p| (p[0].as_f64().unwrap(), p[1].as_f64().unwrap()))
            .collect()
    }

    fn check(actual: f64, expected: &serde_json::Value, context: &str) {
        let expected = expected.as_f64().unwrap();
        assert_close(actual, expected, context);
        if expected == 0.0 {
            assert_eq!(
                actual.is_sign_positive(),
                expected.is_sign_positive(),
                "{context}: sign of zero"
            );
        }
    }

    #[test]
    fn matches_golden_fixture() {
        let golden = load_golden("shot_stats");
        let cases = golden["cases"].as_array().unwrap();
        assert!(cases.len() >= 7);
        for case in cases {
            let name = case["name"].as_str().unwrap();
            let pts = points(&case["points"]);

            let stats = compute_stats(&pts);
            let e = &case["stats"];
            assert_eq!(stats.count, e["count"].as_u64().unwrap() as usize, "{name}");
            check(stats.mean_x_mm, &e["mean_x_mm"], name);
            check(stats.mean_y_mm, &e["mean_y_mm"], name);
            check(stats.extreme_spread_mm, &e["extreme_spread_mm"], name);
            check(stats.mean_radius_mm, &e["mean_radius_mm"], name);

            let trace = compute_trace_stats(&pts);
            let e = &case["trace"];
            assert_eq!(
                trace.samples,
                e["samples"].as_u64().unwrap() as usize,
                "{name}"
            );
            check(trace.hold_tremor_mm, &e["hold_tremor_mm"], name);
            check(trace.trace_length_mm, &e["trace_length_mm"], name);
            check(trace.mean_x_mm, &e["mean_x_mm"], name);
            check(trace.mean_y_mm, &e["mean_y_mm"], name);

            let inside = case["inside"].as_array().unwrap();
            assert_eq!(inside.len(), 8, "{name}");
            for item in inside {
                let c = &item["centre"];
                let got = time_inside_radius(
                    &pts,
                    item["radius_mm"].as_f64().unwrap(),
                    (c[0].as_f64().unwrap(), c[1].as_f64().unwrap()),
                );
                check(got, &item["fraction"], name);
            }
        }
    }

    proptest! {
        #[test]
        fn invariants_hold(
            pts in prop::collection::vec((-1000.0f64..1000.0, -1000.0f64..1000.0), 0..40),
            radius in 0.0f64..2000.0,
            centre in (-1000.0f64..1000.0, -1000.0f64..1000.0),
        ) {
            let stats = compute_stats(&pts);
            prop_assert!(stats.extreme_spread_mm >= 0.0);
            if pts.len() >= 2 {
                prop_assert!(stats.mean_radius_mm <= stats.extreme_spread_mm + 1e-9);
            }
            let fraction = time_inside_radius(&pts, radius, centre);
            prop_assert!((0.0..=1.0).contains(&fraction));
        }
    }
}
