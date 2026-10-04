//! Port of `tracking/detector_tuning.py`. The grid search is pure, and the
//! Hough pass it scores with is supplied through [`HoughScorer`].

use crate::detector::DetectorSettings;
use crate::frame::Frame;
use crate::frame_ops::{adjust_image, bgr_to_grey};

/// Brightness and contrast the optimiser settled on. The default is the identity.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ImageAdjustment {
    pub brightness: f64,
    pub contrast: f64,
}

impl Default for ImageAdjustment {
    fn default() -> Self {
        ImageAdjustment {
            brightness: 0.0,
            contrast: 1.0,
        }
    }
}

/// The values the search walks. The default is Python's.
#[derive(Debug, Clone, PartialEq)]
pub struct TuningGrid {
    pub block_sizes: Vec<i32>,
    pub offsets: Vec<i32>,
    pub blurs: Vec<i32>,
    pub closing_kernels: Vec<i32>,
    pub brightness_steps: Vec<f64>,
    pub contrast_steps: Vec<f64>,
}

impl Default for TuningGrid {
    fn default() -> Self {
        TuningGrid {
            block_sizes: vec![15, 31],
            offsets: vec![2, 8],
            blurs: vec![3, 5],
            closing_kernels: vec![0, 5],
            brightness_steps: vec![-100.0, -50.0, 0.0, 50.0, 100.0],
            contrast_steps: vec![0.5, 1.0, 1.5, 2.0],
        }
    }
}

/// `settings` is `None` when nothing scored above zero, and then the
/// adjustment is the identity and the score is 0.
#[derive(Debug, Clone, PartialEq)]
pub struct TuningResult {
    pub settings: Option<DetectorSettings>,
    pub adjustment: ImageAdjustment,
    pub score: f64,
}

/// Python `_evaluate_cell`'s Hough pass for one blur kernel on the adjusted
/// grey frame. Returns the confidence of a detection inside the tracking
/// region, or `None`.
pub trait HoughScorer {
    fn hough_score(&mut self, adjusted: &Frame, blur: i32, base: &DetectorSettings) -> Option<f64>;
}

/// Python `optimise_detector_settings`. Cells run brightness-major. Within a
/// cell a blur only wins with a strictly higher score, and across cells the
/// first best cell wins, as Python's `max` does. An empty `block_sizes`,
/// `offsets` or `closing_kernels` keeps the base value, where Python raises.
pub fn optimise_detector_settings(
    frame: &Frame,
    base: &DetectorSettings,
    grid: &TuningGrid,
    scorer: &mut impl HoughScorer,
) -> TuningResult {
    let none = TuningResult {
        settings: None,
        adjustment: ImageAdjustment::default(),
        score: 0.0,
    };
    if frame.is_empty() {
        return none;
    }
    let grey = bgr_to_grey(frame.clone());
    let mut best: Option<TuningResult> = None;
    for &brightness in &grid.brightness_steps {
        for &contrast in &grid.contrast_steps {
            let cell = evaluate_cell(
                &grey,
                ImageAdjustment {
                    brightness,
                    contrast,
                },
                base,
                grid,
                scorer,
            );
            if best.as_ref().is_none_or(|b| cell.score > b.score) {
                best = Some(cell);
            }
        }
    }
    match best {
        Some(b) if b.settings.is_some() => b,
        _ => none,
    }
}

fn evaluate_cell(
    grey: &Frame,
    adjustment: ImageAdjustment,
    base: &DetectorSettings,
    grid: &TuningGrid,
    scorer: &mut impl HoughScorer,
) -> TuningResult {
    let adjusted = adjust_image(grey.clone(), adjustment.brightness, adjustment.contrast);
    let mut best_score = 0.0;
    let mut best_settings = None;
    for &blur in &grid.blurs {
        let Some(score) = scorer.hough_score(&adjusted, blur, base) else {
            continue;
        };
        if score <= best_score {
            continue;
        }
        best_score = score;
        best_settings = Some(DetectorSettings {
            adaptive_block_size: grid
                .block_sizes
                .first()
                .copied()
                .unwrap_or(base.adaptive_block_size),
            adaptive_offset: grid
                .offsets
                .first()
                .copied()
                .unwrap_or(base.adaptive_offset),
            closing_kernel_px: grid
                .closing_kernels
                .last()
                .copied()
                .unwrap_or(base.closing_kernel_px),
            blur_kernel: blur,
            ..base.clone()
        });
    }
    TuningResult {
        settings: best_settings,
        adjustment,
        score: best_score,
    }
}

#[cfg(test)]
mod tests {
    use std::collections::VecDeque;

    use serde_json::Value;
    use testkit::{assert_close, load_golden};

    use super::*;
    use crate::frame::PixelFormat;
    use crate::test_support::{f64_at, settings_from_json};

    /// Replays the Hough scores Python saw, in call order.
    struct Replay {
        scores: VecDeque<Option<f64>>,
        calls: Vec<(i32, u8)>,
    }

    impl HoughScorer for Replay {
        fn hough_score(
            &mut self,
            adjusted: &Frame,
            blur: i32,
            _base: &DetectorSettings,
        ) -> Option<f64> {
            self.calls.push((blur, adjusted.data()[0]));
            self.scores
                .pop_front()
                .expect("more Hough calls than Python made")
        }
    }

    fn ints(v: &Value) -> Vec<i32> {
        v.as_array()
            .unwrap()
            .iter()
            .map(|x| i32::try_from(x.as_i64().unwrap()).unwrap())
            .collect()
    }

    fn floats(v: &Value) -> Vec<f64> {
        v.as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect()
    }

    fn grid(v: &Value) -> TuningGrid {
        TuningGrid {
            block_sizes: ints(&v["block_sizes"]),
            offsets: ints(&v["offsets"]),
            blurs: ints(&v["blurs"]),
            closing_kernels: ints(&v["closing_kernels"]),
            brightness_steps: floats(&v["brightness_steps"]),
            contrast_steps: floats(&v["contrast_steps"]),
        }
    }

    #[test]
    fn search_matches_python() {
        let golden = load_golden("detector_tuning");
        let cases = golden["cases"].as_array().unwrap();
        assert!(cases.len() >= 10);
        for case in cases {
            let name = case["name"].as_str().unwrap();
            let grid = grid(&case["grid"]);
            let mut replay = Replay {
                scores: case["scores"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(Value::as_f64)
                    .collect(),
                calls: Vec::new(),
            };
            let frame = if case["empty"].as_bool().unwrap() {
                Frame::filled(0, 0, PixelFormat::Grey, 0).unwrap()
            } else {
                Frame::filled(4, 4, PixelFormat::Grey, 100).unwrap()
            };
            let result = optimise_detector_settings(
                &frame,
                &settings_from_json(&case["base"]),
                &grid,
                &mut replay,
            );

            assert!(
                replay.scores.is_empty(),
                "{name}: fewer Hough calls than Python made"
            );
            let cells = if frame.is_empty() {
                0
            } else {
                grid.brightness_steps.len() * grid.contrast_steps.len()
            };
            let expected_blurs: Vec<i32> = (0..cells).flat_map(|_| grid.blurs.clone()).collect();
            let blurs: Vec<i32> = replay.calls.iter().map(|c| c.0).collect();
            let pixels: Vec<u8> = replay.calls.iter().map(|c| c.1).collect();
            assert_eq!(blurs, expected_blurs, "{name}: call order");
            let want_pixels: Vec<u8> = case["pixels"]
                .as_array()
                .unwrap()
                .iter()
                .map(|p| u8::try_from(p.as_u64().unwrap()).unwrap())
                .collect();
            assert_eq!(pixels, want_pixels, "{name}: adjusted frames");

            match (&result.settings, &case["settings"]) {
                (None, Value::Null) => {}
                (Some(got), want) if !want.is_null() => {
                    assert_eq!(got, &settings_from_json(want), "{name}")
                }
                (got, want) => panic!("{name}: settings {got:?} vs {want}"),
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
    fn empty_grid_lists_fall_back_to_the_base_settings() {
        let base = DetectorSettings {
            adaptive_block_size: 41,
            adaptive_offset: 7,
            closing_kernel_px: 9,
            ..DetectorSettings::default()
        };
        let grid = TuningGrid {
            block_sizes: vec![],
            offsets: vec![],
            closing_kernels: vec![],
            blurs: vec![5],
            brightness_steps: vec![0.0],
            contrast_steps: vec![1.0],
        };
        let mut replay = Replay {
            scores: VecDeque::from([Some(0.5)]),
            calls: Vec::new(),
        };
        let result = optimise_detector_settings(
            &Frame::filled(2, 2, PixelFormat::Grey, 0).unwrap(),
            &base,
            &grid,
            &mut replay,
        );
        let settings = result.settings.unwrap();
        assert_eq!(
            (
                settings.adaptive_block_size,
                settings.adaptive_offset,
                settings.closing_kernel_px,
                settings.blur_kernel
            ),
            (41, 7, 9, 5)
        );
    }

    #[test]
    fn empty_steps_return_no_settings() {
        let grid = TuningGrid {
            brightness_steps: vec![],
            ..TuningGrid::default()
        };
        let mut replay = Replay {
            scores: VecDeque::new(),
            calls: Vec::new(),
        };
        let result = optimise_detector_settings(
            &Frame::filled(2, 2, PixelFormat::Grey, 0).unwrap(),
            &DetectorSettings::default(),
            &grid,
            &mut replay,
        );
        assert_eq!(
            result,
            TuningResult {
                settings: None,
                adjustment: ImageAdjustment::default(),
                score: 0.0
            }
        );
    }
}
