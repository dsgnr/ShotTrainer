//! The per-frame path of `AppController._on_frame` and
//! `_on_frame_processed`. Each frame is converted to grey, transformed and
//! tracked, and the result carries the overlay state the camera view draws.

use shottrainer_settings::Preferences;
use shottrainer_tracking::detector::{DetectorSettings, TargetDetector};
use shottrainer_tracking::frame::Frame;
use shottrainer_tracking::frame_ops::{FrameTransform, adjust_image, bgr_to_grey, transform_frame};
use shottrainer_tracking::log_limit::RepeatLimiter;
use shottrainer_tracking::models::{Detection, TrackingSample};
use shottrainer_tracking::tracker::Tracker;

/// Python refreshes the header status line every fifth frame.
const STATUS_REFRESH_EVERY_N_FRAMES: i64 = 5;
const DEFAULT_CIRCLE_DIAMETER_MM: f64 = 60.0;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrackingStatus {
    Idle,
    Tracking,
    Lost,
    Rejected,
}

/// A circle drawn on the camera view, in frame pixels.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Marker {
    pub x_px: f64,
    pub y_px: f64,
    pub radius_px: f64,
}

/// One processed frame and everything drawn over it.
#[derive(Debug, Clone, PartialEq)]
pub struct FrameView {
    /// Greyscale, after the rotation, flips, brightness and contrast.
    pub frame: Frame,
    pub timestamp: f64,
    pub frame_id: i64,
    pub status: TrackingStatus,
    pub aim: Option<Marker>,
    /// A circle found outside the tracking region.
    pub rejected: Option<Marker>,
    pub zero_px: Option<(f64, f64)>,
    /// The live trace point to append, absent while a saved session is on
    /// display.
    pub trace_point_mm: Option<(f64, f64)>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct FrameOutcome {
    pub view: FrameView,
    pub sample: Option<TrackingSample>,
    /// The header status line, refreshed every fifth tracked frame.
    pub status_text: Option<String>,
}

/// Turns a detection with any non-finite number into not-found. One NaN
/// centre or radius would otherwise stay in the tracker's moving averages
/// until the circle diameter changes, as it does in Python.
pub struct FiniteDetections<D> {
    inner: D,
    warnings: RepeatLimiter,
}

impl<D: TargetDetector> FiniteDetections<D> {
    pub fn new(inner: D) -> Self {
        FiniteDetections {
            inner,
            warnings: RepeatLimiter::default(),
        }
    }
}

fn is_finite(d: &Detection) -> bool {
    [
        d.x_px,
        d.y_px,
        d.radius_px,
        d.confidence,
        d.semi_major_px,
        d.semi_minor_px,
        d.angle_degrees,
    ]
    .iter()
    .all(|v| v.is_finite())
}

impl<D: TargetDetector> TargetDetector for FiniteDetections<D> {
    fn detect(&mut self, frame: &Frame) -> Detection {
        let detection = self.inner.detect(frame);
        if is_finite(&detection) {
            return detection;
        }
        if let Some(text) = self
            .warnings
            .check("Ignoring a detection with non-finite values")
        {
            log::warn!("{text}");
        }
        Detection::default()
    }

    fn reset_lock(&mut self) {
        self.inner.reset_lock();
    }

    fn settings(&self) -> &DetectorSettings {
        self.inner.settings()
    }

    fn set_settings(&mut self, settings: DetectorSettings) {
        self.inner.set_settings(settings);
    }
}

pub type LiveTracker = Tracker<FiniteDetections<Box<dyn TargetDetector>>>;

pub struct FramePipeline {
    tracker: LiveTracker,
    transform: FrameTransform,
    latest_unadjusted: Option<Frame>,
    warnings: RepeatLimiter,
}

impl FramePipeline {
    /// A diameter the tracker refuses falls back to 60 mm. Validated
    /// preferences never hold one.
    pub fn new(prefs: &Preferences, detector: Box<dyn TargetDetector>) -> Self {
        let diameter = if prefs.circle_diameter_mm > 0.0 && prefs.circle_diameter_mm.is_finite() {
            prefs.circle_diameter_mm
        } else {
            DEFAULT_CIRCLE_DIAMETER_MM
        };
        let tracker = match Tracker::new(diameter, FiniteDetections::new(detector)) {
            Ok(tracker) => tracker,
            Err(_) => unreachable!("the diameter was checked above"),
        };
        FramePipeline {
            tracker,
            transform: FrameTransform::default(),
            latest_unadjusted: None,
            warnings: RepeatLimiter::default(),
        }
    }

    pub fn tracker(&self) -> &LiveTracker {
        &self.tracker
    }

    pub fn tracker_mut(&mut self) -> &mut LiveTracker {
        &mut self.tracker
    }

    pub fn transform(&self) -> &FrameTransform {
        &self.transform
    }

    pub fn set_transform(&mut self, transform: FrameTransform) {
        self.transform = transform;
    }

    /// The latest frame before brightness and contrast, which the optimiser
    /// searches from.
    pub fn latest_unadjusted(&self) -> Option<&Frame> {
        self.latest_unadjusted.as_ref()
    }

    /// Processes one camera frame. `None` when the transform fails, which
    /// only an unsupported rotation can cause.
    pub fn process(
        &mut self,
        frame: Frame,
        timestamp: f64,
        frame_id: i64,
        reviewing: bool,
    ) -> Option<FrameOutcome> {
        let geometric = FrameTransform {
            brightness: 0.0,
            contrast: 1.0,
            ..self.transform.clone()
        };
        let unadjusted = match transform_frame(bgr_to_grey(frame), &geometric) {
            Ok(frame) => frame,
            Err(error) => {
                if let Some(text) = self.warnings.check(&format!("Dropping a frame: {error}")) {
                    log::warn!("{text}");
                }
                return None;
            }
        };
        self.latest_unadjusted = Some(unadjusted.clone());
        let frame = adjust_image(
            unadjusted,
            self.transform.brightness,
            self.transform.contrast,
        );
        let sample = self.tracker.process(&frame, timestamp, Some(frame_id));
        let mut view = FrameView {
            frame,
            timestamp,
            frame_id,
            status: TrackingStatus::Lost,
            aim: None,
            rejected: None,
            zero_px: None,
            trace_point_mm: None,
        };
        let Some(sample) = sample else {
            if let Some(d) = self
                .tracker
                .last_detection()
                .filter(|d| d.rejected_outside_region)
            {
                view.status = TrackingStatus::Rejected;
                view.rejected = Some(Marker {
                    x_px: d.x_px,
                    y_px: d.y_px,
                    radius_px: d.radius_px,
                });
            }
            return Some(FrameOutcome {
                view,
                sample: None,
                status_text: None,
            });
        };
        view.status = TrackingStatus::Tracking;
        view.aim = Some(Marker {
            x_px: sample.x_px,
            y_px: sample.y_px,
            radius_px: self.tracker.last_radius_px(),
        });
        view.zero_px = self.tracker.zero_pixel();
        if !reviewing && let (Some(x), Some(y)) = (sample.x_mm, sample.y_mm) {
            view.trace_point_mm = Some((x, y));
        }
        let status_text = (sample.frame_id.rem_euclid(STATUS_REFRESH_EVERY_N_FRAMES) == 0)
            .then(|| self.status_text());
        Some(FrameOutcome {
            view,
            sample: Some(sample),
            status_text,
        })
    }

    /// Python `_refresh_tracking_status`.
    pub fn status_text(&self) -> String {
        match self.tracker.mm_per_pixel() {
            None => "Acquiring target...".to_owned(),
            Some(mm_per_px) => format!(
                "Tracking {:.0} mm circle - {mm_per_px:.3} mm/px",
                self.tracker.circle_diameter_mm()
            ),
        }
    }
}

#[cfg(test)]
mod tests {
    use shottrainer_tracking::frame::PixelFormat;

    use super::*;
    use crate::fakes::{ScriptedDetector, circle_at};

    fn pipeline() -> (FramePipeline, ScriptedDetector) {
        let detector = ScriptedDetector::default();
        let handle = detector.share();
        (
            FramePipeline::new(&Preferences::default(), Box::new(detector)),
            handle,
        )
    }

    fn grey(width: u32, height: u32) -> Frame {
        Frame::filled(width, height, PixelFormat::Grey, 100).unwrap()
    }

    #[test]
    fn a_found_target_is_tracked_and_traced() {
        let (mut pipeline, detector) = pipeline();
        detector.push(circle_at(330.0, 240.0));
        let out = pipeline.process(grey(640, 480), 1.5, 1, false).unwrap();
        let sample = out.sample.unwrap();
        assert_eq!((sample.timestamp, sample.frame_id), (1.5, 1));
        assert_eq!(out.view.status, TrackingStatus::Tracking);
        assert_eq!(
            out.view.aim,
            Some(Marker {
                x_px: 330.0,
                y_px: 240.0,
                radius_px: 30.0
            })
        );
        // 10 px right of centre on a 60 mm circle of radius 30 px is 10 mm,
        // and the default trace sign reverses it.
        assert_eq!(out.view.trace_point_mm, Some((-10.0, -0.0)));
        assert_eq!(out.view.rejected, None);
        assert_eq!(out.status_text, None, "frame 1 is not a refresh frame");
    }

    #[test]
    fn colour_frames_are_converted_to_grey_first() {
        let (mut pipeline, detector) = pipeline();
        let bgr = Frame::new(1, 1, PixelFormat::Bgr, vec![255, 0, 0]).unwrap();
        let out = pipeline.process(bgr, 0.0, 1, false).unwrap();
        assert_eq!(out.view.frame.format(), PixelFormat::Grey);
        assert_eq!(out.view.frame.data(), [29], "OpenCV's weight for blue");
        assert_eq!(detector.seen.lock().unwrap()[0].format(), PixelFormat::Grey);
    }

    #[test]
    fn rotation_happens_before_the_unadjusted_copy_and_brightness_after() {
        let (mut pipeline, detector) = pipeline();
        pipeline.set_transform(FrameTransform {
            rotation_degrees: 90,
            brightness: 50.0,
            ..FrameTransform::default()
        });
        let out = pipeline.process(grey(4, 2), 0.0, 1, false).unwrap();
        let unadjusted = pipeline.latest_unadjusted().unwrap();
        assert_eq!((unadjusted.width(), unadjusted.height()), (2, 4));
        assert!(unadjusted.data().iter().all(|&v| v == 100));
        assert!(out.view.frame.data().iter().all(|&v| v == 150));
        assert_eq!(detector.seen.lock().unwrap()[0], out.view.frame);
    }

    #[test]
    fn an_unsupported_rotation_drops_the_frame() {
        let (mut pipeline, _) = pipeline();
        pipeline.set_transform(FrameTransform {
            rotation_degrees: 45,
            ..FrameTransform::default()
        });
        assert_eq!(pipeline.process(grey(4, 4), 0.0, 1, false), None);
    }

    #[test]
    fn a_lost_target_and_a_rejected_one_are_told_apart() {
        let (mut pipeline, detector) = pipeline();
        let out = pipeline.process(grey(64, 64), 0.0, 1, false).unwrap();
        assert_eq!((out.view.status, out.sample), (TrackingStatus::Lost, None));
        detector.push(Detection {
            rejected_outside_region: true,
            x_px: 5.0,
            y_px: 6.0,
            radius_px: 7.0,
            ..Detection::default()
        });
        let out = pipeline.process(grey(64, 64), 0.1, 2, false).unwrap();
        assert_eq!(out.view.status, TrackingStatus::Rejected);
        assert_eq!(
            out.view.rejected,
            Some(Marker {
                x_px: 5.0,
                y_px: 6.0,
                radius_px: 7.0
            })
        );
        assert_eq!((out.view.aim, out.view.trace_point_mm), (None, None));
    }

    #[test]
    fn no_trace_point_while_reviewing() {
        let (mut pipeline, detector) = pipeline();
        detector.push(circle_at(320.0, 240.0));
        let out = pipeline.process(grey(640, 480), 0.0, 1, true).unwrap();
        assert!(out.sample.is_some());
        assert_eq!(out.view.trace_point_mm, None);
    }

    #[test]
    fn the_status_line_refreshes_every_fifth_tracked_frame() {
        let (mut pipeline, detector) = pipeline();
        detector.push(circle_at(320.0, 240.0));
        let out = pipeline.process(grey(640, 480), 0.0, 5, false).unwrap();
        assert_eq!(
            out.status_text.as_deref(),
            Some("Tracking 60 mm circle - 1.000 mm/px")
        );
        let out = pipeline.process(grey(640, 480), 0.0, 10, false).unwrap();
        assert_eq!(out.status_text, None, "no sample, no refresh");
        assert_eq!(
            FramePipeline::new(
                &Preferences::default(),
                Box::new(ScriptedDetector::default())
            )
            .status_text(),
            "Acquiring target..."
        );
    }

    #[test]
    fn the_zero_marker_follows_the_offset() {
        let (mut pipeline, detector) = pipeline();
        pipeline.tracker_mut().set_zero_offset(3.0, 0.0);
        detector.push(circle_at(320.0, 240.0));
        let out = pipeline.process(grey(640, 480), 0.0, 1, false).unwrap();
        assert_eq!(out.view.zero_px, Some((323.0, 240.0)));
    }

    #[test]
    fn a_non_finite_detection_does_not_poison_the_smoothing() {
        let nan = Detection {
            x_px: f64::NAN,
            ..circle_at(320.0, 240.0)
        };
        // The tracker on its own keeps the NaN in its moving average.
        let mut plain = Tracker::new(60.0, ScriptedDetector::default()).unwrap();
        plain.detector().push(nan.clone());
        plain.detector().push(circle_at(320.0, 240.0));
        plain.process(&grey(640, 480), 0.0, None);
        let poisoned = plain.process(&grey(640, 480), 0.1, None).unwrap();
        assert!(poisoned.x_px.is_nan());

        let (mut pipeline, detector) = pipeline();
        detector.push(nan);
        detector.push(circle_at(320.0, 240.0));
        let first = pipeline.process(grey(640, 480), 0.0, 1, false).unwrap();
        assert_eq!(
            (first.view.status, first.sample),
            (TrackingStatus::Lost, None)
        );
        let second = pipeline.process(grey(640, 480), 0.1, 2, false).unwrap();
        assert_eq!(second.sample.unwrap().x_px, 320.0);
    }

    #[test]
    fn a_bad_diameter_falls_back_to_sixty_millimetres() {
        let prefs = Preferences {
            circle_diameter_mm: f64::NAN,
            ..Preferences::default()
        };
        let pipeline = FramePipeline::new(&prefs, Box::new(ScriptedDetector::default()));
        assert_eq!(pipeline.tracker().circle_diameter_mm(), 60.0);
    }
}
