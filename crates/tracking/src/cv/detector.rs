//! Port of `CircleTargetDetector` from `tracking/detector.py`.

use std::f64::consts::PI;

use opencv::core::{self, Mat, Point, Point2f, Rect, Scalar, Size, Vec3f, Vector};
use opencv::imgproc;
use opencv::prelude::*;

use super::compat::{
    arc_length, bounding_rect, contour_area, fit_ellipse, min_enclosing_circle, moments,
};
use super::mat::frame_as_mat;
use crate::detector::{
    DetectorSettings, Region, SoftLock, TargetDetector, ellipse_axes, hough_confidence,
    lock_adjusted_score, lock_window,
};
use crate::frame::{Frame, PixelFormat};
use crate::models::Detection;

/// Hough circle detection with a contour fallback and a soft lock.
#[derive(Debug, Default)]
pub struct CircleTargetDetector {
    settings: DetectorSettings,
    lock: SoftLock,
}

impl CircleTargetDetector {
    pub fn new(settings: DetectorSettings) -> Self {
        CircleTargetDetector {
            settings,
            lock: SoftLock::default(),
        }
    }

    pub fn lock_position(&self) -> Option<(f64, f64)> {
        self.lock.position
    }

    pub fn consecutive_misses(&self) -> i64 {
        self.lock.consecutive_misses
    }

    fn try_detect(&mut self, frame: &Frame) -> opencv::Result<Detection> {
        if frame.is_empty() {
            return Ok(Detection::default());
        }
        let s = self.settings.clone();
        let grey = grey_mat(frame)?;
        let grey = blur(grey, s.blur_kernel)?;

        if let Some(det) = self.try_hough(&grey, &s)? {
            let region = Region::new(mat_width(&grey), mat_height(&grey), &s);
            if region.contains(det.x_px, det.y_px) {
                self.lock.hit(det.x_px, det.y_px);
                return Ok(det);
            }
        }
        self.detect_contour(&grey, &s)
    }

    /// Python `_try_hough`. `grey` is the blurred greyscale frame.
    pub(crate) fn try_hough(
        &self,
        grey: &Mat,
        s: &DetectorSettings,
    ) -> opencv::Result<Option<Detection>> {
        let (w, h) = (mat_width(grey), mat_height(grey));
        let region = Region::new(w, h, s);
        let (search_rect, ox, oy) = search_rect(self.lock.position, grey, s);
        // OpenCV filters read the parent's pixels beyond a Rust submatrix edge,
        // but cv2 treats a numpy slice as a standalone image and replicates its
        // border. Cloning gives Hough the same standalone image.
        let search = Mat::roi(grey, search_rect)?.try_clone()?;

        let min_dist = s.min_radius_px.saturating_mul(2).max(30);
        let mut circles = Vector::<Vec3f>::new();
        imgproc::hough_circles(
            &search,
            &mut circles,
            imgproc::HOUGH_GRADIENT,
            1.0,
            f64::from(min_dist),
            50.0,
            30.0,
            s.min_radius_px,
            s.max_radius_px,
        )?;

        let lock_radius = s.lock_radius_px * s.lock_search_radius_factor;
        let (mut best_cx, mut best_cy, mut best_r) = (0.0, 0.0, 0.0);
        for circle in circles.iter() {
            let cx = f64::from(circle[0]) + f64::from(ox);
            let cy = f64::from(circle[1]) + f64::from(oy);
            let r = f64::from(circle[2]);
            if r < f64::from(s.min_radius_px) || r > f64::from(s.max_radius_px) {
                continue;
            }
            if !region.contains(cx, cy) {
                continue;
            }
            if let Some((lx, ly)) = self.lock.position
                && (cx - lx).hypot(cy - ly) > lock_radius
            {
                continue;
            }
            if r > best_r {
                (best_cx, best_cy, best_r) = (cx, cy, r);
            }
        }
        if best_r <= 0.0 {
            return Ok(None);
        }
        let confidence = edge_confidence(grey, best_cx, best_cy, best_r)?;
        Ok(Some(Detection {
            found: true,
            x_px: best_cx,
            y_px: best_cy,
            radius_px: best_r,
            confidence,
            ..Detection::default()
        }))
    }

    /// Python `_detect_contour`.
    fn detect_contour(&mut self, grey: &Mat, s: &DetectorSettings) -> opencv::Result<Detection> {
        let block = 3.max(s.adaptive_block_size | 1);
        let mut binary = Mat::default();
        imgproc::adaptive_threshold(
            grey,
            &mut binary,
            255.0,
            imgproc::ADAPTIVE_THRESH_MEAN_C,
            imgproc::THRESH_BINARY_INV,
            block,
            f64::from(s.adaptive_offset),
        )?;
        if s.opening_kernel_px >= 3 {
            binary = morphology(&binary, imgproc::MORPH_OPEN, s.opening_kernel_px | 1)?;
        }
        if s.closing_kernel_px >= 3 {
            binary = morphology(&binary, imgproc::MORPH_CLOSE, s.closing_kernel_px | 1)?;
        }

        let (w, h) = (mat_width(grey), mat_height(grey));
        let (search_rect, ox, oy) = search_rect(self.lock.position, &binary, s);
        let search = Mat::roi(&binary, search_rect)?;
        let mut found = Vector::<Vector<Point>>::new();
        imgproc::find_contours(
            &search,
            &mut found,
            imgproc::RETR_EXTERNAL,
            imgproc::CHAIN_APPROX_SIMPLE,
            Point::new(ox, oy),
        )?;

        let max_candidates = i64::from(s.max_candidates);
        let min_points = 8_i64.max(2 * i64::from(s.min_radius_px));
        let mut contours: Vec<Vector<Point>> = found.into_iter().collect();
        if contours.len() as i64 > max_candidates {
            contours.retain(|c| c.len() as i64 >= min_points);
        }
        let mut candidates = Vec::with_capacity(contours.len());
        for contour in contours {
            let area = contour_area(&contour, false)?;
            candidates.push((contour, area));
        }
        if candidates.len() as i64 > max_candidates {
            // `heapq.nlargest` equals a stable descending sort, so equal
            // areas keep their contour order.
            candidates.sort_by(|a, b| b.1.total_cmp(&a.1));
            candidates.truncate(usize::try_from(s.max_candidates).unwrap_or(0));
        }

        let region = Region::new(w, h, s);
        let min_side = s.min_radius_px.saturating_mul(2);
        let max_side = s.max_radius_px.saturating_mul(2);
        let mut best = Detection::default();
        let mut best_score = 0.0;
        let mut best_contour: Option<&Vector<Point>> = None;
        let mut best_off_region: Option<(f64, f64, f64, f64)> = None;

        for (contour, area) in &candidates {
            let area = *area;
            let bbox = bounding_rect(contour)?;
            if bbox.width < min_side || bbox.height < min_side {
                continue;
            }
            if bbox.width > max_side && bbox.height > max_side {
                continue;
            }
            if area <= 0.0 {
                continue;
            }
            let perimeter = arc_length(contour, true)?;
            if perimeter <= 0.0 {
                continue;
            }
            let radius_est = (area / PI).sqrt();
            if radius_est < f64::from(s.min_radius_px) || radius_est > f64::from(s.max_radius_px) {
                continue;
            }
            let circularity = 4.0 * PI * area / (perimeter * perimeter);
            if circularity < s.min_circularity {
                continue;
            }
            let mut centre = Point2f::default();
            let mut enclosing_r = 0.0_f32;
            min_enclosing_circle(contour, &mut centre, &mut enclosing_r)?;
            let enclosing_r = f64::from(enclosing_r);
            if enclosing_r <= 0.0 {
                continue;
            }
            let m = moments(contour, false)?;
            if m.m00 <= 0.0 {
                continue;
            }
            let cx = m.m10 / m.m00;
            let cy = m.m01 / m.m00;
            let fill = area / (PI * enclosing_r * enclosing_r);
            let unboosted = circularity * fill;
            if !region.contains(cx, cy) {
                if best_off_region.is_none_or(|b| unboosted > b.3) {
                    best_off_region = Some((cx, cy, enclosing_r, unboosted));
                }
                continue;
            }
            let score = lock_adjusted_score(unboosted, (cx, cy), self.lock.position, s);
            if score > best_score {
                best_score = score;
                best_contour = Some(contour);
                best = Detection {
                    found: true,
                    x_px: cx,
                    y_px: cy,
                    radius_px: enclosing_r,
                    confidence: score,
                    ..Detection::default()
                };
            }
        }

        if best.found {
            if let Some(contour) = best_contour {
                best = with_ellipse_fit(best, contour);
            }
            self.lock.hit(best.x_px, best.y_px);
            return Ok(best);
        }
        self.lock.miss(s.lock_release_after_misses);
        if let Some((cx, cy, r, score)) = best_off_region {
            return Ok(Detection {
                found: false,
                x_px: cx,
                y_px: cy,
                radius_px: r,
                confidence: score,
                rejected_outside_region: true,
                ..Detection::default()
            });
        }
        Ok(best)
    }
}

impl TargetDetector for CircleTargetDetector {
    /// An OpenCV error is logged and reported as no detection, leaving the
    /// lock untouched, as an exception in the Python frame slot would.
    fn detect(&mut self, frame: &Frame) -> Detection {
        self.try_detect(frame).unwrap_or_else(|error| {
            log::warn!("Circle detector failed: {error}");
            Detection::default()
        })
    }

    fn reset_lock(&mut self) {
        self.lock = SoftLock::default();
    }

    fn settings(&self) -> &DetectorSettings {
        &self.settings
    }

    fn set_settings(&mut self, settings: DetectorSettings) {
        self.settings = settings;
    }
}

pub(crate) fn grey_mat(frame: &Frame) -> opencv::Result<Mat> {
    match frame.format() {
        PixelFormat::Grey => frame_as_mat(frame)?.try_clone(),
        PixelFormat::Bgr => {
            frame_as_mat(&crate::frame_ops::bgr_to_grey(frame.clone()))?.try_clone()
        }
    }
}

/// Gaussian blur with sigma 0, skipped for kernels below 3 as in Python.
pub(crate) fn blur(grey: Mat, kernel: i32) -> opencv::Result<Mat> {
    if kernel < 3 {
        return Ok(grey);
    }
    let mut out = Mat::default();
    imgproc::gaussian_blur_def(&grey, &mut out, Size::new(kernel, kernel), 0.0)?;
    Ok(out)
}

fn morphology(binary: &Mat, op: i32, size: i32) -> opencv::Result<Mat> {
    let kernel = imgproc::get_structuring_element(
        imgproc::MORPH_ELLIPSE,
        Size::new(size, size),
        Point::new(-1, -1),
    )?;
    let mut out = Mat::default();
    imgproc::morphology_ex_def(binary, &mut out, op, &kernel)?;
    Ok(out)
}

/// The lock window when one applies, otherwise the whole matrix, with its offset.
fn search_rect(lock: Option<(f64, f64)>, mat: &Mat, s: &DetectorSettings) -> (Rect, i32, i32) {
    let (w, h) = (mat.cols(), mat.rows());
    match lock.and_then(|lock| lock_window(lock, mat_width(mat), mat_height(mat), s)) {
        Some((x0, y0, x1, y1)) => (Rect::new(x0, y0, x1 - x0, y1 - y0), x0, y0),
        None => (Rect::new(0, 0, w, h), 0, 0),
    }
}

fn edge_confidence(grey: &Mat, cx: f64, cy: f64, r: f64) -> opencv::Result<f64> {
    let size = grey.size()?;
    let centre = Point::new(cx as i32, cy as i32);
    let band = |outer: f64, inner: Option<f64>| -> opencv::Result<Mat> {
        let mut mask = Mat::new_size_with_default(size, core::CV_8UC1, Scalar::all(0.0))?;
        let outer_r = if inner.is_none() {
            1.max((r * outer) as i32)
        } else {
            (r * outer) as i32
        };
        imgproc::circle(
            &mut mask,
            centre,
            outer_r,
            Scalar::all(255.0),
            imgproc::FILLED,
            imgproc::LINE_8,
            0,
        )?;
        if let Some(inner) = inner {
            imgproc::circle(
                &mut mask,
                centre,
                (r * inner) as i32,
                Scalar::all(0.0),
                imgproc::FILLED,
                imgproc::LINE_8,
                0,
            )?;
        }
        Ok(mask)
    };
    let inner_band = band(0.99, Some(0.85))?;
    let outer_band = band(1.15, Some(1.01))?;
    let interior = band(0.9, None)?;
    if core::count_non_zero(&inner_band)? == 0
        || core::count_non_zero(&outer_band)? == 0
        || core::count_non_zero(&interior)? == 0
    {
        return Ok(0.0);
    }
    let inner_mean = core::mean(grey, &inner_band)?[0];
    let outer_mean = core::mean(grey, &outer_band)?[0];
    let mut mean = Vector::<f64>::new();
    let mut stddev = Vector::<f64>::new();
    core::mean_std_dev(grey, &mut mean, &mut stddev, &interior)?;
    Ok(hough_confidence(inner_mean, outer_mean, stddev.get(0)?))
}

fn with_ellipse_fit(detection: Detection, contour: &Vector<Point>) -> Detection {
    if contour.len() < 5 {
        return detection;
    }
    let Ok(fit) = fit_ellipse(contour) else {
        return detection;
    };
    match ellipse_axes(
        f64::from(fit.size.width),
        f64::from(fit.size.height),
        f64::from(fit.angle),
    ) {
        Some((semi_major_px, semi_minor_px, angle_degrees)) => Detection {
            semi_major_px,
            semi_minor_px,
            angle_degrees,
            ..detection
        },
        None => detection,
    }
}

fn mat_width(mat: &Mat) -> u32 {
    u32::try_from(mat.cols()).unwrap_or(0)
}

fn mat_height(mat: &Mat) -> u32 {
    u32::try_from(mat.rows()).unwrap_or(0)
}
#[cfg(test)]
mod tests {
    use testkit::{assert_close, load_golden};

    use super::*;
    use crate::test_support::{assert_detection_close, load_png_frame, settings_from_json};

    #[test]
    fn detector_matches_python() {
        let golden = load_golden("detector");
        let cases = golden["cases"].as_array().unwrap();
        assert!(cases.len() >= 40);
        for case in cases {
            let name = case["name"].as_str().unwrap();
            let mut detector = CircleTargetDetector::new(settings_from_json(&case["settings"]));
            for (i, step) in case["steps"].as_array().unwrap().iter().enumerate() {
                let frame_name = step["frame"].as_str().unwrap();
                let context = format!("{name} step {i} ({frame_name})");
                let got = detector.detect(&load_png_frame(frame_name));
                assert_detection_close(&got, &step["detection"], &context);
                match (detector.lock_position(), &step["lock"]) {
                    (None, serde_json::Value::Null) => {}
                    (Some((x, y)), want) if !want.is_null() => {
                        assert_close(x, want[0].as_f64().unwrap(), &format!("{context} lock x"));
                        assert_close(y, want[1].as_f64().unwrap(), &format!("{context} lock y"));
                    }
                    (got, want) => panic!("{context}: lock {got:?} vs {want}"),
                }
                assert_eq!(
                    detector.consecutive_misses(),
                    step["misses"].as_i64().unwrap(),
                    "{context}"
                );
            }
        }
    }

    #[test]
    fn degenerate_frames_and_settings_do_not_panic() {
        let target = load_png_frame("centred");
        let frames = [
            Frame::filled(0, 0, PixelFormat::Grey, 0),
            Frame::filled(1, 1, PixelFormat::Grey, 0),
            Frame::filled(3, 200, PixelFormat::Bgr, 0),
            target.clone(),
        ];
        let settings = [
            DetectorSettings {
                blur_kernel: 4,
                ..DetectorSettings::default()
            },
            DetectorSettings {
                min_radius_px: 300,
                max_radius_px: 10,
                ..DetectorSettings::default()
            },
            DetectorSettings {
                max_candidates: -1,
                adaptive_block_size: -7,
                ..DetectorSettings::default()
            },
            DetectorSettings {
                region_fraction: f64::NAN,
                lock_radius_px: f64::NAN,
                ..DetectorSettings::default()
            },
        ];
        for s in settings {
            let mut detector = CircleTargetDetector::new(s);
            for frame in &frames {
                let _ = detector.detect(frame);
            }
        }
        let mut detector = CircleTargetDetector::default();
        assert!(detector.detect(&target).found);
        detector.reset_lock();
        assert_eq!(
            (detector.lock_position(), detector.consecutive_misses()),
            (None, 0)
        );
    }
}
