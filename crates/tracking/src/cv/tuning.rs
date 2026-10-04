//! The Hough pass the auto-optimise search scores with.

use opencv::prelude::*;

use super::detector::{CircleTargetDetector, blur, grey_mat};
use crate::detector::{DetectorSettings, Region};
use crate::frame::Frame;
use crate::tuning::HoughScorer;

/// Blurs the adjusted frame, runs Hough from a released lock with the blur
/// setting cleared and applies the region check, as `_evaluate_cell` does.
#[derive(Debug, Default)]
pub struct OpenCvHoughScorer;

impl HoughScorer for OpenCvHoughScorer {
    fn hough_score(
        &mut self,
        adjusted: &Frame,
        blur_kernel: i32,
        base: &DetectorSettings,
    ) -> Option<f64> {
        let run = || -> opencv::Result<Option<f64>> {
            let blurred = blur(grey_mat(adjusted)?, blur_kernel)?;
            let settings = DetectorSettings {
                blur_kernel: 0,
                ..base.clone()
            };
            let detector = CircleTargetDetector::new(settings.clone());
            let Some(det) = detector.try_hough(&blurred, &settings)? else {
                return Ok(None);
            };
            let region = Region::new(
                u32::try_from(blurred.cols()).unwrap_or(0),
                u32::try_from(blurred.rows()).unwrap_or(0),
                &settings,
            );
            Ok(region
                .contains(det.x_px, det.y_px)
                .then_some(det.confidence))
        };
        run().unwrap_or_else(|e| {
            log::warn!("Auto-optimise Hough pass failed: {e}");
            None
        })
    }
}

#[cfg(test)]
mod tests {
    use testkit::{assert_close, load_golden};

    use super::*;
    use crate::detector::TargetDetector;
    use crate::test_support::{f64_at, load_png_frame, settings_from_json};
    use crate::tuning::{TuningGrid, optimise_detector_settings};

    #[test]
    fn optimiser_matches_python() {
        let golden = load_golden("detector");
        for case in golden["tuning"].as_array().unwrap() {
            let name = case["frame"].as_str().unwrap();
            let result = optimise_detector_settings(
                &load_png_frame(name),
                &DetectorSettings::default(),
                &TuningGrid::default(),
                &mut OpenCvHoughScorer,
            );
            match (&result.settings, &case["settings"]) {
                (None, serde_json::Value::Null) => {}
                (Some(got), want) if !want.is_null() => {
                    assert_eq!(got, &settings_from_json(want), "{name}")
                }
                (got, want) => panic!("{name}: {got:?} vs {want}"),
            }
            assert_eq!(
                result.adjustment.brightness,
                case["adjustment"][0].as_f64().unwrap(),
                "{name}"
            );
            assert_eq!(
                result.adjustment.contrast,
                case["adjustment"][1].as_f64().unwrap(),
                "{name}"
            );
            assert_close(result.score, f64_at(case, "score"), name);
        }
    }

    #[test]
    fn the_golden_set_covers_a_colour_frame() {
        assert_eq!(
            load_png_frame("bgr_target").format(),
            crate::frame::PixelFormat::Bgr
        );
        let golden = load_golden("detector");
        assert!(
            golden["tuning"]
                .as_array()
                .unwrap()
                .iter()
                .any(|c| c["frame"] == "bgr_target")
        );
    }

    fn score(frame: &str, blur_kernel: i32, base: &DetectorSettings) -> Option<f64> {
        let grey = crate::frame_ops::bgr_to_grey(load_png_frame(frame));
        OpenCvHoughScorer.hough_score(&grey, blur_kernel, base)
    }

    #[test]
    fn blurs_below_three_leave_the_frame_unblurred() {
        let base = DetectorSettings::default();
        let unblurred = score("rings", 0, &base);
        assert!(unblurred.is_some());
        assert_eq!(score("rings", 1, &base), unblurred);
        assert_eq!(score("rings", 2, &base), unblurred);
        assert_eq!(score("rings", -4, &base), unblurred);
        assert_ne!(score("rings", 5, &base), unblurred);
    }

    #[test]
    fn the_base_blur_setting_does_not_reach_the_hough_run() {
        let heavy = DetectorSettings {
            blur_kernel: 15,
            ..DetectorSettings::default()
        };
        let none = DetectorSettings {
            blur_kernel: 0,
            ..DetectorSettings::default()
        };
        for kernel in [0, 3, 5] {
            assert_eq!(
                score("centred", kernel, &heavy),
                score("centred", kernel, &none),
                "kernel {kernel}"
            );
        }
        assert!(score("centred", 3, &heavy).is_some());
    }

    #[test]
    fn every_call_starts_from_a_released_lock() {
        let base = DetectorSettings::default();
        let grey = |name: &str| crate::frame_ops::bgr_to_grey(load_png_frame(name));
        let (first, second) = (grey("centred"), grey("off_centre"));

        // A locked detector rejects the second frame, so a scorer that kept
        // the lock would differ from a fresh one.
        let mut locked = CircleTargetDetector::new(base.clone());
        let hit = locked.detect(&first);
        assert!(hit.found);
        let blurred = blur(grey_mat(&second).unwrap(), 3).unwrap();
        let held = locked.try_hough(&blurred, &base).unwrap();

        let fresh = OpenCvHoughScorer.hough_score(&second, 3, &base);
        let mut scorer = OpenCvHoughScorer;
        scorer.hough_score(&first, 3, &base);
        assert_eq!(scorer.hough_score(&second, 3, &base), fresh);
        assert!(fresh.is_some());
        assert!(held.is_none());
    }
}
