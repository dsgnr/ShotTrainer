//! Detector settings, the detector trait and the arithmetic shared by every
//! detector implementation. Nothing here needs OpenCV.

use crate::frame::Frame;
use crate::models::Detection;

/// Python `DetectorSettings` in `tracking/detector.py`, field for field.
#[derive(Debug, Clone, PartialEq)]
pub struct DetectorSettings {
    pub min_radius_px: i32,
    pub max_radius_px: i32,
    pub blur_kernel: i32,
    pub min_circularity: f64,
    pub adaptive_block_size: i32,
    pub adaptive_offset: i32,
    pub region_fraction: f64,
    pub lock_radius_px: f64,
    pub lock_boost: f64,
    pub lock_release_after_misses: i32,
    pub opening_kernel_px: i32,
    pub closing_kernel_px: i32,
    pub max_candidates: i32,
    pub lock_search_radius_factor: f64,
}

impl Default for DetectorSettings {
    fn default() -> Self {
        DetectorSettings {
            min_radius_px: 4,
            max_radius_px: 200,
            blur_kernel: 5,
            min_circularity: 0.65,
            adaptive_block_size: 31,
            adaptive_offset: 5,
            region_fraction: 0.7,
            lock_radius_px: 80.0,
            lock_boost: 1.5,
            lock_release_after_misses: 8,
            opening_kernel_px: 3,
            closing_kernel_px: 5,
            max_candidates: 200,
            lock_search_radius_factor: 2.0,
        }
    }
}

/// Finds the target in one frame. Implementations keep a soft lock between
/// calls, so frames must be passed in capture order.
pub trait TargetDetector: Send {
    fn detect(&mut self, frame: &Frame) -> Detection;
    fn reset_lock(&mut self);
    fn settings(&self) -> &DetectorSettings;
    fn set_settings(&mut self, settings: DetectorSettings);
}

impl<D: TargetDetector + ?Sized> TargetDetector for Box<D> {
    fn detect(&mut self, frame: &Frame) -> Detection {
        (**self).detect(frame)
    }
    fn reset_lock(&mut self) {
        (**self).reset_lock()
    }
    fn settings(&self) -> &DetectorSettings {
        (**self).settings()
    }
    fn set_settings(&mut self, settings: DetectorSettings) {
        (**self).set_settings(settings)
    }
}

/// Python `max(0.05, min(1.0, fraction))`, which maps NaN to 1.0.
pub fn effective_region_fraction(fraction: f64) -> f64 {
    0.05_f64.max(1.0_f64.min(fraction))
}

/// The centred acceptance box.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Region {
    pub centre_x: f64,
    pub centre_y: f64,
    pub half_width: f64,
    pub half_height: f64,
}

impl Region {
    pub fn new(width: u32, height: u32, settings: &DetectorSettings) -> Self {
        let fraction = effective_region_fraction(settings.region_fraction);
        let (w, h) = (f64::from(width), f64::from(height));
        Region {
            centre_x: w / 2.0,
            centre_y: h / 2.0,
            half_width: w * fraction / 2.0,
            half_height: h * fraction / 2.0,
        }
    }

    /// Written as the negation of Python's rejection test so NaN behaves the same.
    pub fn contains(&self, x: f64, y: f64) -> bool {
        !((x - self.centre_x).abs() > self.half_width
            || (y - self.centre_y).abs() > self.half_height)
    }
}

/// Pixel box `(x0, y0, x1, y1)` searched while a lock is held, or `None` when
/// the clipped box is empty and the whole frame is searched.
pub fn lock_window(
    lock: (f64, f64),
    width: u32,
    height: u32,
    settings: &DetectorSettings,
) -> Option<(i32, i32, i32, i32)> {
    let radius =
        1.0_f64.max(settings.lock_radius_px) * 1.0_f64.max(settings.lock_search_radius_factor);
    let (lx, ly) = lock;
    // `as i32` truncates towards zero like Python's `int()`.
    let x0 = 0.max((lx - radius) as i32);
    let y0 = 0.max((ly - radius) as i32);
    let x1 = i32::try_from(width)
        .unwrap_or(i32::MAX)
        .min((lx + radius) as i32);
    let y1 = i32::try_from(height)
        .unwrap_or(i32::MAX)
        .min((ly + radius) as i32);
    (x1 > x0 && y1 > y0).then_some((x0, y0, x1, y1))
}

/// Soft lock boost inside the lock radius and quadratic damping outside it.
pub fn lock_adjusted_score(
    score: f64,
    centroid: (f64, f64),
    lock: Option<(f64, f64)>,
    settings: &DetectorSettings,
) -> f64 {
    let Some((lx, ly)) = lock else {
        return score;
    };
    let d = (centroid.0 - lx).hypot(centroid.1 - ly);
    let radius = 1.0_f64.max(settings.lock_radius_px);
    if d <= radius {
        score * (1.0 + (settings.lock_boost - 1.0) * (1.0 - d / radius))
    } else {
        score * (1.0 / (1.0 + ((d - radius) / radius).powi(2)))
    }
}

/// `(semi_major, semi_minor, major_angle_degrees)` from the full axes and
/// angle `fitEllipse` reports, or `None` for a degenerate fit.
pub fn ellipse_axes(axis_a: f64, axis_b: f64, angle: f64) -> Option<(f64, f64, f64)> {
    if axis_a <= 0.0 || axis_b <= 0.0 {
        return None;
    }
    if axis_a >= axis_b {
        Some((axis_a / 2.0, axis_b / 2.0, angle))
    } else {
        // `rem_euclid` matches Python's `%` for a positive divisor.
        Some((axis_b / 2.0, axis_a / 2.0, (angle + 90.0).rem_euclid(180.0)))
    }
}

/// Python `_hough_edge_confidence` after the band means and the interior
/// standard deviation are measured.
pub fn hough_confidence(inner_mean: f64, outer_mean: f64, interior_stddev: f64) -> f64 {
    let edge_score = (outer_mean - inner_mean).abs() / 255.0;
    let uniformity_score = 0.0_f64.max(1.0 - interior_stddev / 30.0);
    let dark_saturation = 0.0_f64.max(1.0 - inner_mean.min(outer_mean) / 60.0);
    let light_saturation = 0.0_f64.max((inner_mean.max(outer_mean) - 195.0) / 60.0);
    let saturation_score = (dark_saturation + light_saturation) / 2.0;
    edge_score * uniformity_score * (0.5 + 0.5 * saturation_score)
}

/// Lock position and the miss counter that releases it.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct SoftLock {
    pub position: Option<(f64, f64)>,
    pub consecutive_misses: i64,
}

impl SoftLock {
    pub fn hit(&mut self, x: f64, y: f64) {
        self.position = Some((x, y));
        self.consecutive_misses = 0;
    }

    /// Counts a contour-path miss and drops the lock once the count reaches
    /// `release_after`. The count keeps rising while no lock is held, as in Python.
    pub fn miss(&mut self, release_after: i32) {
        self.consecutive_misses = self.consecutive_misses.saturating_add(1);
        if self.position.is_some() && self.consecutive_misses >= i64::from(release_after) {
            self.position = None;
        }
    }
}

#[cfg(test)]
mod tests {
    use testkit::assert_close;

    use super::*;

    #[test]
    fn defaults_match_python() {
        let s = DetectorSettings::default();
        assert_eq!(
            (
                s.min_radius_px,
                s.max_radius_px,
                s.blur_kernel,
                s.adaptive_block_size
            ),
            (4, 200, 5, 31)
        );
        assert_eq!(
            (
                s.adaptive_offset,
                s.lock_release_after_misses,
                s.opening_kernel_px
            ),
            (5, 8, 3)
        );
        assert_eq!((s.closing_kernel_px, s.max_candidates), (5, 200));
        assert_eq!(
            (
                s.min_circularity,
                s.region_fraction,
                s.lock_radius_px,
                s.lock_boost
            ),
            (0.65, 0.7, 80.0, 1.5)
        );
        assert_eq!(s.lock_search_radius_factor, 2.0);
    }

    #[test]
    fn region_fraction_is_clamped_like_python() {
        for (input, expected) in [
            (0.7, 0.7),
            (0.0, 0.05),
            (-1.0, 0.05),
            (2.0, 1.0),
            (0.05, 0.05),
        ] {
            assert_eq!(effective_region_fraction(input), expected, "{input}");
        }
        assert_eq!(effective_region_fraction(f64::NAN), 1.0);
    }

    #[test]
    fn region_edges_are_inclusive() {
        let region = Region::new(640, 480, &DetectorSettings::default());
        assert_eq!(
            (
                region.centre_x,
                region.centre_y,
                region.half_width,
                region.half_height
            ),
            (320.0, 240.0, 224.0, 168.0)
        );
        assert!(region.contains(544.0, 240.0));
        assert!(!region.contains(544.0001, 240.0));
        assert!(region.contains(320.0, 72.0));
        assert!(!region.contains(320.0, 71.9));
        assert!(region.contains(f64::NAN, 240.0));
    }

    #[test]
    fn lock_window_truncates_and_clips_like_python() {
        let s = DetectorSettings::default();
        assert_eq!(
            lock_window((320.0, 240.0), 640, 480, &s),
            Some((160, 80, 480, 400))
        );
        assert_eq!(
            lock_window((10.7, 5.2), 640, 480, &s),
            Some((0, 0, 170, 165))
        );
        assert_eq!(
            lock_window((700.0, 240.0), 640, 480, &s),
            Some((540, 80, 640, 400))
        );
        assert_eq!(lock_window((900.0, 240.0), 640, 480, &s), None);
        let tiny = DetectorSettings {
            lock_radius_px: 0.5,
            lock_search_radius_factor: 0.5,
            ..s
        };
        assert_eq!(lock_window((5.5, 5.5), 640, 480, &tiny), Some((4, 4, 6, 6)));
    }

    #[test]
    fn lock_score_matches_python() {
        let s = DetectorSettings::default();
        let lock = Some((320.0, 240.0));
        assert_eq!(lock_adjusted_score(0.8, (1.0, 2.0), None, &s), 0.8);
        for (score, centroid, expected) in [
            (0.8, (320.0, 240.0), 1.2000000000000002),
            (0.8, (360.0, 240.0), 1.0),
            (0.8, (480.0, 240.0), 0.4),
            (0.6, (323.0, 244.0), 0.88125),
            (0.9, (100.0, 100.0), 0.14740089006010867),
        ] {
            assert_close(
                lock_adjusted_score(score, centroid, lock, &s),
                expected,
                "lock score",
            );
        }
    }

    #[test]
    fn ellipse_axes_pick_the_major_axis() {
        assert_eq!(ellipse_axes(60.0, 36.0, 10.0), Some((30.0, 18.0, 10.0)));
        assert_eq!(ellipse_axes(36.0, 60.0, 10.0), Some((30.0, 18.0, 100.0)));
        assert_eq!(ellipse_axes(36.0, 60.0, 170.0), Some((30.0, 18.0, 80.0)));
        assert_eq!(ellipse_axes(36.0, 60.0, -95.0), Some((30.0, 18.0, 175.0)));
        assert_eq!(ellipse_axes(10.0, 10.0, 45.0), Some((5.0, 5.0, 45.0)));
        assert_eq!(ellipse_axes(0.0, 5.0, 0.0), None);
        assert_eq!(ellipse_axes(5.0, -1.0, 0.0), None);
    }

    #[test]
    fn hough_confidence_matches_python() {
        for (inner, outer, stddev, expected) in [
            (10.0, 240.0, 0.0, 0.8080065359477124),
            (100.0, 100.0, 5.0, 0.0),
            (0.0, 255.0, 30.0, 0.0),
            (200.0, 50.0, 3.0, 0.2977941176470588),
            (37.5, 212.25, 4.75, 0.3839253216911765),
        ] {
            assert_close(
                hough_confidence(inner, outer, stddev),
                expected,
                "confidence",
            );
        }
    }

    #[test]
    fn soft_lock_releases_after_the_configured_misses() {
        let mut lock = SoftLock::default();
        lock.miss(3);
        assert_eq!((lock.position, lock.consecutive_misses), (None, 1));
        lock.hit(1.0, 2.0);
        assert_eq!(lock.consecutive_misses, 0);
        lock.miss(3);
        lock.miss(3);
        assert_eq!(lock.position, Some((1.0, 2.0)));
        lock.miss(3);
        assert_eq!((lock.position, lock.consecutive_misses), (None, 3));
        lock.miss(3);
        assert_eq!(lock.consecutive_misses, 4);
        lock.hit(5.0, 6.0);
        lock.miss(0);
        assert_eq!(lock.position, None);
        lock.consecutive_misses = i64::MAX;
        lock.miss(3);
        assert_eq!(lock.consecutive_misses, i64::MAX);
    }
}
