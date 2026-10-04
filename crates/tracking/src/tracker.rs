//! Port of `Tracker` from `tracking/tracker.py`. Converts detections to aim
//! points in millimetres.

use crate::detector::{TargetDetector, effective_region_fraction};
use crate::frame::Frame;
use crate::models::{Detection, TrackingSample};

const RADIUS_EMA_ALPHA: f64 = 0.1;
const CENTROID_EMA_ALPHA: f64 = 0.1;
const MIN_INFORMATIVE_RADIUS_PX: f64 = 4.0;

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum TrackerError {
    #[error("circle_diameter_mm must be positive")]
    InvalidDiameter,
}

pub struct Tracker<D: TargetDetector> {
    detector: D,
    diameter_mm: f64,
    frame_id: i64,
    last_sample: Option<TrackingSample>,
    last_detection: Option<Detection>,
    last_radius_px: f64,
    smoothed_cx_px: Option<f64>,
    smoothed_cy_px: Option<f64>,
    smoothed_major_px: Option<f64>,
    smoothed_minor_px: Option<f64>,
    last_angle_rad: f64,
    zero_offset_mm: (f64, f64),
    trace_signs: (f64, f64),
}

/// Python accepts NaN because `nan <= 0` is false. Rust also rejects
/// non-finite diameters, which validated preferences never contain.
fn check_diameter(diameter_mm: f64) -> Result<f64, TrackerError> {
    if diameter_mm > 0.0 && diameter_mm.is_finite() {
        Ok(diameter_mm)
    } else {
        Err(TrackerError::InvalidDiameter)
    }
}

impl<D: TargetDetector> Tracker<D> {
    pub fn new(circle_diameter_mm: f64, detector: D) -> Result<Self, TrackerError> {
        Ok(Tracker {
            detector,
            diameter_mm: check_diameter(circle_diameter_mm)?,
            frame_id: 0,
            last_sample: None,
            last_detection: None,
            last_radius_px: 0.0,
            smoothed_cx_px: None,
            smoothed_cy_px: None,
            smoothed_major_px: None,
            smoothed_minor_px: None,
            last_angle_rad: 0.0,
            zero_offset_mm: (0.0, 0.0),
            trace_signs: (-1.0, -1.0),
        })
    }

    pub fn detector(&self) -> &D {
        &self.detector
    }

    pub fn detector_mut(&mut self) -> &mut D {
        &mut self.detector
    }

    /// Resets the smoothed axes and centroid so the next frame starts afresh.
    pub fn set_circle_diameter_mm(&mut self, diameter_mm: f64) -> Result<(), TrackerError> {
        self.diameter_mm = check_diameter(diameter_mm)?;
        self.smoothed_major_px = None;
        self.smoothed_minor_px = None;
        self.smoothed_cx_px = None;
        self.smoothed_cy_px = None;
        Ok(())
    }

    pub fn set_trace_inversion(&mut self, invert_x: bool, invert_y: bool) {
        self.trace_signs = (
            if invert_x { 1.0 } else { -1.0 },
            if invert_y { 1.0 } else { -1.0 },
        );
    }

    pub fn set_region_fraction(&mut self, fraction: f64) {
        let mut settings = self.detector.settings().clone();
        settings.region_fraction = effective_region_fraction(fraction);
        self.detector.set_settings(settings);
    }

    pub fn set_zero_offset(&mut self, x_mm: f64, y_mm: f64) {
        self.zero_offset_mm = (x_mm, y_mm);
    }

    pub fn clear_zero_offset(&mut self) {
        self.zero_offset_mm = (0.0, 0.0);
    }

    pub fn zero_offset_mm(&self) -> (f64, f64) {
        self.zero_offset_mm
    }

    /// Adds the last sample's aim point to the zero offset. Returns `false`
    /// when there is no sample with millimetre coordinates yet.
    pub fn zero_at_last_sample(&mut self) -> bool {
        let Some(TrackingSample {
            x_mm: Some(x),
            y_mm: Some(y),
            ..
        }) = self.last_sample
        else {
            return false;
        };
        let (ox, oy) = self.zero_offset_mm;
        self.zero_offset_mm = (x + ox, y + oy);
        true
    }

    /// Pixel position of the zero point, using a round-circle scale.
    pub fn zero_pixel(&self) -> Option<(f64, f64)> {
        if self.zero_offset_mm == (0.0, 0.0) {
            return None;
        }
        let sample = self.last_sample.as_ref()?;
        if self.last_radius_px <= 0.0 {
            return None;
        }
        let radius_mm = self.diameter_mm / 2.0;
        let mm_per_px = radius_mm / self.last_radius_px;
        if mm_per_px <= 0.0 {
            return None;
        }
        let (ox, oy) = self.zero_offset_mm;
        let (sx, sy) = self.trace_signs;
        let dx_px = -ox / (sx * mm_per_px);
        let dy_px = -oy / (sy * mm_per_px);
        Some((sample.x_px + dx_px, sample.y_px + dy_px))
    }

    /// Runs the detector and returns the aim point, or `None` when no target
    /// was found. A supplied `frame_id` is recorded as is and does not move
    /// the internal counter.
    pub fn process(
        &mut self,
        frame: &Frame,
        timestamp: f64,
        frame_id: Option<i64>,
    ) -> Option<TrackingSample> {
        let sample_frame_id = match frame_id {
            Some(id) => id,
            None => {
                self.frame_id += 1;
                self.frame_id
            }
        };
        let det = self.detector.detect(frame);
        self.last_detection = Some(det.clone());
        if !det.found {
            self.last_radius_px = 0.0;
            return None;
        }
        self.last_radius_px = det.radius_px;
        let (major_px, minor_px) = self.update_smoothed_axes(&det);
        let (cx_px, cy_px) = self.update_smoothed_centroid(det.x_px, det.y_px);
        let (x_mm, y_mm) = self.aim_in_mm(
            cx_px,
            cy_px,
            major_px,
            minor_px,
            frame.width(),
            frame.height(),
        );
        let sample = TrackingSample {
            timestamp,
            x_px: cx_px,
            y_px: cy_px,
            x_mm: Some(x_mm),
            y_mm: Some(y_mm),
            confidence: det.confidence,
            frame_id: sample_frame_id,
        };
        self.last_sample = Some(sample.clone());
        Some(sample)
    }

    pub fn last_radius_px(&self) -> f64 {
        self.last_radius_px
    }

    pub fn last_detection(&self) -> Option<&Detection> {
        self.last_detection.as_ref()
    }

    pub fn last_sample(&self) -> Option<&TrackingSample> {
        self.last_sample.as_ref()
    }

    /// Mean millimetres per pixel over both smoothed axes, for display.
    pub fn mm_per_pixel(&self) -> Option<f64> {
        let (major, minor) = (self.smoothed_major_px?, self.smoothed_minor_px?);
        if major <= 0.0 || minor <= 0.0 {
            return None;
        }
        let major_mm_per_px = self.diameter_mm / (2.0 * major);
        let minor_mm_per_px = self.diameter_mm / (2.0 * minor);
        Some((major_mm_per_px + minor_mm_per_px) / 2.0)
    }

    pub fn circle_diameter_mm(&self) -> f64 {
        self.diameter_mm
    }

    fn update_smoothed_axes(&mut self, det: &Detection) -> (f64, f64) {
        if det.confidence <= 0.0 {
            return self.fallback_axes(det.radius_px);
        }
        let (major_in, minor_in) = if det.semi_major_px > 0.0 && det.semi_minor_px > 0.0 {
            self.last_angle_rad = det.angle_degrees.to_radians();
            (det.semi_major_px, det.semi_minor_px)
        } else {
            (det.radius_px, det.radius_px)
        };
        if major_in < MIN_INFORMATIVE_RADIUS_PX {
            return self.fallback_axes(det.radius_px);
        }
        let a = RADIUS_EMA_ALPHA;
        let major = match self.smoothed_major_px {
            None => major_in,
            Some(prev) => (1.0 - a) * prev + a * major_in,
        };
        let minor = match self.smoothed_minor_px {
            None => minor_in,
            Some(prev) => (1.0 - a) * prev + a * minor_in,
        };
        self.smoothed_major_px = Some(major);
        self.smoothed_minor_px = Some(minor);
        (major, minor)
    }

    fn update_smoothed_centroid(&mut self, cx_px: f64, cy_px: f64) -> (f64, f64) {
        let a = CENTROID_EMA_ALPHA;
        let (cx, cy) = match (self.smoothed_cx_px, self.smoothed_cy_px) {
            (Some(px), Some(py)) => ((1.0 - a) * px + a * cx_px, (1.0 - a) * py + a * cy_px),
            _ => (cx_px, cy_px),
        };
        self.smoothed_cx_px = Some(cx);
        self.smoothed_cy_px = Some(cy);
        (cx, cy)
    }

    fn fallback_axes(&self, radius_px: f64) -> (f64, f64) {
        if let (Some(major), Some(minor)) = (self.smoothed_major_px, self.smoothed_minor_px) {
            return (major, minor);
        }
        // Python `max(radius_px, 4.0)` keeps a NaN radius, which `f64::max` would not.
        let radius = if MIN_INFORMATIVE_RADIUS_PX > radius_px {
            MIN_INFORMATIVE_RADIUS_PX
        } else {
            radius_px
        };
        (radius, radius)
    }

    fn aim_in_mm(
        &self,
        cx_px: f64,
        cy_px: f64,
        major_px: f64,
        minor_px: f64,
        width: u32,
        height: u32,
    ) -> (f64, f64) {
        let dx_px = cx_px - f64::from(width) / 2.0;
        let dy_px = cy_px - f64::from(height) / 2.0;
        let radius_mm = self.diameter_mm / 2.0;
        let mm_per_px_major = radius_mm / major_px;
        let mm_per_px_minor = radius_mm / minor_px;
        let (sin_t, cos_t) = (self.last_angle_rad.sin(), self.last_angle_rad.cos());
        let local_major = dx_px * cos_t + dy_px * sin_t;
        let local_minor = -dx_px * sin_t + dy_px * cos_t;
        let local_major_mm = local_major * mm_per_px_major;
        let local_minor_mm = local_minor * mm_per_px_minor;
        let x_mm_image = local_major_mm * cos_t - local_minor_mm * sin_t;
        let y_mm_image = local_major_mm * sin_t + local_minor_mm * cos_t;
        let (sx, sy) = self.trace_signs;
        let (ox, oy) = self.zero_offset_mm;
        (sx * x_mm_image - ox, sy * y_mm_image - oy)
    }
}

#[cfg(test)]
mod tests {
    use serde_json::Value;
    use testkit::{assert_close, load_golden};

    use super::*;
    use crate::detector::DetectorSettings;
    use crate::frame::PixelFormat;
    use crate::test_support::{detection_from_json, f64_at};

    /// Returns whatever detection the test queued for the next frame.
    struct Scripted {
        settings: DetectorSettings,
        next: Detection,
    }

    impl TargetDetector for Scripted {
        fn detect(&mut self, _frame: &Frame) -> Detection {
            self.next.clone()
        }
        fn reset_lock(&mut self) {}
        fn settings(&self) -> &DetectorSettings {
            &self.settings
        }
        fn set_settings(&mut self, settings: DetectorSettings) {
            self.settings = settings;
        }
    }

    fn scripted() -> Scripted {
        Scripted {
            settings: DetectorSettings::default(),
            next: Detection::default(),
        }
    }

    fn number(v: &Value) -> f64 {
        match v {
            Value::String(s) if s == "nan" => f64::NAN,
            Value::String(s) if s == "inf" => f64::INFINITY,
            Value::String(s) if s == "-inf" => f64::NEG_INFINITY,
            other => other.as_f64().unwrap(),
        }
    }

    fn assert_option_close(got: Option<f64>, want: &Value, context: &str) {
        match (got, want) {
            (None, Value::Null) => {}
            (Some(g), w) if !w.is_null() => assert_close(g, w.as_f64().unwrap(), context),
            _ => panic!("{context}: got {got:?}, want {want}"),
        }
    }

    fn assert_state(t: &Tracker<Scripted>, state: &Value, context: &str) {
        assert_option_close(
            t.mm_per_pixel(),
            &state["mm_per_pixel"],
            &format!("{context} mm_per_pixel"),
        );
        match (t.zero_pixel(), &state["zero_pixel"]) {
            (None, Value::Null) => {}
            (Some((x, y)), w) if !w.is_null() => {
                assert_close(
                    x,
                    w[0].as_f64().unwrap(),
                    &format!("{context} zero_pixel x"),
                );
                assert_close(
                    y,
                    w[1].as_f64().unwrap(),
                    &format!("{context} zero_pixel y"),
                );
            }
            (got, want) => panic!("{context}: zero_pixel {got:?} vs {want}"),
        }
        assert_close(t.last_radius_px(), f64_at(state, "last_radius_px"), context);
        let (ox, oy) = t.zero_offset_mm();
        assert_close(ox, state["zero_offset_mm"][0].as_f64().unwrap(), context);
        assert_close(oy, state["zero_offset_mm"][1].as_f64().unwrap(), context);
        assert_close(
            t.detector().settings().region_fraction,
            f64_at(state, "region_fraction"),
            context,
        );
        assert_close(t.circle_diameter_mm(), f64_at(state, "diameter"), context);
    }

    #[test]
    fn tracker_matches_python() {
        let golden = load_golden("tracker");
        let cases = golden["cases"].as_array().unwrap();
        assert!(cases.len() >= 10);
        for case in cases {
            let name = case["name"].as_str().unwrap();
            let mut t = Tracker::new(f64_at(case, "diameter"), scripted()).unwrap();
            for (i, step) in case["steps"].as_array().unwrap().iter().enumerate() {
                let context = format!("{name} step {i}");
                match step["op"].as_str().unwrap() {
                    "process" => {
                        let dim = |k: &str| u32::try_from(step[k].as_u64().unwrap()).unwrap();
                        let frame =
                            Frame::filled(dim("w"), dim("h"), PixelFormat::Grey, 0).unwrap();
                        t.detector_mut().next = detection_from_json(&step["det"]);
                        let got = t.process(&frame, f64_at(step, "ts"), step["frame_id"].as_i64());
                        match (&got, &step["sample"]) {
                            (None, Value::Null) => {}
                            (Some(s), want) if !want.is_null() => {
                                for (g, k) in [
                                    (s.timestamp, "timestamp"),
                                    (s.x_px, "x_px"),
                                    (s.y_px, "y_px"),
                                    (s.confidence, "confidence"),
                                ] {
                                    assert_close(g, f64_at(want, k), &format!("{context} {k}"));
                                }
                                assert_option_close(
                                    s.x_mm,
                                    &want["x_mm"],
                                    &format!("{context} x_mm"),
                                );
                                assert_option_close(
                                    s.y_mm,
                                    &want["y_mm"],
                                    &format!("{context} y_mm"),
                                );
                                assert_eq!(
                                    s.frame_id,
                                    want["frame_id"].as_i64().unwrap(),
                                    "{context}"
                                );
                            }
                            _ => panic!("{context}: got {got:?}, want {}", step["sample"]),
                        }
                        assert_eq!(
                            t.last_detection(),
                            Some(&detection_from_json(&step["det"])),
                            "{context}"
                        );
                    }
                    "diameter" => {
                        let result = t.set_circle_diameter_mm(number(&step["value"]));
                        assert_eq!(
                            result.is_err(),
                            step["error"].as_bool().unwrap(),
                            "{context}"
                        );
                    }
                    "invert" => t.set_trace_inversion(
                        step["x"].as_bool().unwrap(),
                        step["y"].as_bool().unwrap(),
                    ),
                    "zero" => t.set_zero_offset(f64_at(step, "x"), f64_at(step, "y")),
                    "clear_zero" => t.clear_zero_offset(),
                    "zero_last" => assert_eq!(
                        t.zero_at_last_sample(),
                        step["result"].as_bool().unwrap(),
                        "{context}"
                    ),
                    "region" => t.set_region_fraction(number(&step["value"])),
                    other => panic!("unknown op {other}"),
                }
                assert_state(&t, &step["state"], &context);
            }
        }
    }

    #[test]
    fn constructor_rejects_what_python_rejects() {
        let golden = load_golden("tracker");
        for case in golden["constructor"].as_array().unwrap() {
            let result = Tracker::new(number(&case["diameter"]), scripted());
            assert_eq!(result.is_err(), case["error"].as_bool().unwrap(), "{case}");
        }
    }

    #[test]
    fn non_finite_diameters_are_rejected() {
        for d in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            assert_eq!(
                Tracker::new(d, scripted()).err(),
                Some(TrackerError::InvalidDiameter)
            );
            let mut t = Tracker::new(60.0, scripted()).unwrap();
            assert!(t.set_circle_diameter_mm(d).is_err());
            assert_eq!(t.circle_diameter_mm(), 60.0);
        }
    }

    #[test]
    fn a_degenerate_detection_never_panics() {
        let mut t = Tracker::new(60.0, scripted()).unwrap();
        for d in [
            Detection {
                found: true,
                radius_px: 0.0,
                confidence: 1.0,
                ..Detection::default()
            },
            Detection {
                found: true,
                radius_px: f64::NAN,
                x_px: f64::NAN,
                confidence: f64::NAN,
                ..Detection::default()
            },
            Detection {
                found: true,
                radius_px: 1e308,
                x_px: -1e308,
                confidence: 1.0,
                ..Detection::default()
            },
        ] {
            t.detector_mut().next = d;
            let _ = t.process(
                &Frame::filled(0, 0, PixelFormat::Grey, 0).unwrap(),
                0.0,
                None,
            );
            let _ = (t.mm_per_pixel(), t.zero_pixel(), t.zero_at_last_sample());
        }
    }
}
