//! Per-shot aiming figures taken from the trace before the trigger pull.

use shottrainer_tracking::models::TrackingSample;

/// The final stretch before the shot that the hold figures cover.
const HOLD_WINDOW_S: f64 = 1.0;

/// Ring radii in millimetres, measured from the face centre.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AimRings {
    /// The outermost scoring ring. Aiming time starts when the trace enters it.
    pub outer_radius_mm: f64,
    /// The largest ring that scores ten.
    pub ten_radius_mm: f64,
    /// A user-chosen radius for the second hold figure.
    pub custom_radius_mm: Option<f64>,
}

/// Each figure is `None` when the trace or the shot position it needs is
/// missing. Percentages run from 0 to 100.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct AimMetrics {
    /// Seconds from the last entry into the outer ring to the shot. A trace
    /// that starts inside the ring gives a lower bound.
    pub aiming_time_s: Option<f64>,
    /// Time in the ten ring around the face centre over the last second.
    pub ten_ring_hold_pct: Option<f64>,
    /// Time in a ten-ring-sized circle around the mean aim point over the last second.
    pub mean_ten_ring_hold_pct: Option<f64>,
    /// As `mean_ten_ring_hold_pct`, for the custom radius.
    pub mean_custom_ring_hold_pct: Option<f64>,
    /// Distance from the mean aim point over the last second to the shot.
    pub shot_offset_mm: Option<f64>,
}

fn percent_within(points: &[(f64, f64)], centre: (f64, f64), radius_mm: f64) -> f64 {
    let inside = points
        .iter()
        .filter(|p| (p.0 - centre.0).hypot(p.1 - centre.1) <= radius_mm)
        .count();
    inside as f64 * 100.0 / points.len() as f64
}

/// `trace` is in time order and may extend past the shot, which is ignored.
/// Samples without a mapped position are skipped.
pub fn compute_aim_metrics(
    trace: &[TrackingSample],
    shot_ts: f64,
    shot_mm: Option<(f64, f64)>,
    rings: &AimRings,
) -> AimMetrics {
    let mapped: Vec<(f64, f64, f64)> = trace
        .iter()
        .filter(|s| s.timestamp <= shot_ts)
        .filter_map(|s| Some((s.timestamp, s.x_mm?, s.y_mm?)))
        .collect();

    let trailing_inside = mapped
        .iter()
        .rev()
        .take_while(|p| p.1.hypot(p.2) <= rings.outer_radius_mm)
        .last();
    let aiming_time_s = trailing_inside.map(|p| shot_ts - p.0);

    let last_second: Vec<(f64, f64)> = mapped
        .iter()
        .filter(|p| p.0 >= shot_ts - HOLD_WINDOW_S)
        .map(|p| (p.1, p.2))
        .collect();
    if last_second.is_empty() {
        return AimMetrics {
            aiming_time_s,
            ..AimMetrics::default()
        };
    }
    let n = last_second.len() as f64;
    let mean = (
        last_second.iter().map(|p| p.0).sum::<f64>() / n,
        last_second.iter().map(|p| p.1).sum::<f64>() / n,
    );
    AimMetrics {
        aiming_time_s,
        ten_ring_hold_pct: Some(percent_within(
            &last_second,
            (0.0, 0.0),
            rings.ten_radius_mm,
        )),
        mean_ten_ring_hold_pct: Some(percent_within(&last_second, mean, rings.ten_radius_mm)),
        mean_custom_ring_hold_pct: rings
            .custom_radius_mm
            .map(|r| percent_within(&last_second, mean, r)),
        shot_offset_mm: shot_mm.map(|s| (s.0 - mean.0).hypot(s.1 - mean.1)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const RINGS: AimRings = AimRings {
        outer_radius_mm: 100.0,
        ten_radius_mm: 5.0,
        custom_radius_mm: Some(10.0),
    };

    fn sample(ts: f64, x: f64, y: f64) -> TrackingSample {
        let mut s = TrackingSample::new(ts, 0.0, 0.0);
        s.x_mm = Some(x);
        s.y_mm = Some(y);
        s
    }

    #[test]
    fn aiming_time_restarts_after_leaving_the_outer_ring() {
        let trace = [
            sample(0.0, 0.0, 0.0),
            sample(1.0, 200.0, 0.0),
            sample(2.0, 50.0, 0.0),
            sample(4.0, 0.0, 0.0),
        ];
        let m = compute_aim_metrics(&trace, 5.0, None, &RINGS);
        assert_eq!(m.aiming_time_s, Some(3.0));
    }

    #[test]
    fn no_aiming_time_when_the_trace_ends_outside_the_outer_ring() {
        let trace = [sample(0.0, 0.0, 0.0), sample(1.0, 200.0, 0.0)];
        assert_eq!(
            compute_aim_metrics(&trace, 1.0, None, &RINGS).aiming_time_s,
            None
        );
    }

    #[test]
    fn holds_cover_only_the_last_second_and_ignore_later_samples() {
        let trace = [
            sample(0.0, 50.0, 0.0),
            sample(4.0, 0.0, 0.0),
            sample(4.5, 8.0, 0.0),
            sample(5.0, 0.0, 0.0),
            sample(6.0, 80.0, 0.0),
        ];
        let m = compute_aim_metrics(&trace, 5.0, Some((3.0, 4.0)), &RINGS);
        // Points 0, 8, 0 give a mean of 8/3. The 8 is outside the 5 mm ring
        // around the centre and around the mean, but inside the 10 mm ring.
        assert!((m.ten_ring_hold_pct.unwrap() - 200.0 / 3.0).abs() < 1e-9);
        assert!((m.mean_ten_ring_hold_pct.unwrap() - 200.0 / 3.0).abs() < 1e-9);
        assert_eq!(m.mean_custom_ring_hold_pct, Some(100.0));
        let offset = (3.0 - 8.0 / 3.0_f64).hypot(4.0);
        assert!((m.shot_offset_mm.unwrap() - offset).abs() < 1e-9);
    }

    #[test]
    fn missing_inputs_leave_figures_empty() {
        assert_eq!(
            compute_aim_metrics(&[], 1.0, None, &RINGS),
            AimMetrics::default()
        );
        let trace = [sample(0.9, 0.0, 0.0)];
        let rings = AimRings {
            custom_radius_mm: None,
            ..RINGS
        };
        let m = compute_aim_metrics(&trace, 1.0, None, &rings);
        assert_eq!(m.mean_custom_ring_hold_pct, None);
        assert_eq!(m.shot_offset_mm, None);
        let unmapped = [TrackingSample::new(0.9, 0.0, 0.0)];
        assert_eq!(
            compute_aim_metrics(&unmapped, 1.0, None, &RINGS),
            AimMetrics::default()
        );
    }
}
