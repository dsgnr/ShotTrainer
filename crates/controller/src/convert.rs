//! Conversions between the settings stores and the types the services use.
//! The tracking and settings crates may not depend on each other, so their
//! two `DetectorSettings` types meet only here.

use std::cmp::Ordering;

use shottrainer_audio::models::ShotDetectorSettings;
use shottrainer_core::services::scoring::{
    ScoreOptions, ScoringDirection, ScoringRing, score_shot,
};
use shottrainer_core::services::shot_coordinator::ShotCoordinatorSettings;
use shottrainer_settings::Preferences;
use shottrainer_settings::stores::DetectorSettings as StoredDetectorSettings;
use shottrainer_settings::target_faces::{TargetFace, get_face};
use shottrainer_tracking::detector::DetectorSettings;
use shottrainer_tracking::frame_ops::FrameTransform;

pub fn detector_from_store(s: &StoredDetectorSettings) -> DetectorSettings {
    DetectorSettings {
        min_radius_px: s.min_radius_px,
        max_radius_px: s.max_radius_px,
        blur_kernel: s.blur_kernel,
        min_circularity: s.min_circularity,
        adaptive_block_size: s.adaptive_block_size,
        adaptive_offset: s.adaptive_offset,
        region_fraction: s.region_fraction,
        lock_radius_px: s.lock_radius_px,
        lock_boost: s.lock_boost,
        lock_release_after_misses: s.lock_release_after_misses,
        opening_kernel_px: s.opening_kernel_px,
        closing_kernel_px: s.closing_kernel_px,
        max_candidates: s.max_candidates,
        lock_search_radius_factor: s.lock_search_radius_factor,
    }
}

pub fn detector_to_store(s: &DetectorSettings) -> StoredDetectorSettings {
    StoredDetectorSettings {
        min_radius_px: s.min_radius_px,
        max_radius_px: s.max_radius_px,
        blur_kernel: s.blur_kernel,
        min_circularity: s.min_circularity,
        adaptive_block_size: s.adaptive_block_size,
        adaptive_offset: s.adaptive_offset,
        region_fraction: s.region_fraction,
        lock_radius_px: s.lock_radius_px,
        lock_boost: s.lock_boost,
        lock_release_after_misses: s.lock_release_after_misses,
        opening_kernel_px: s.opening_kernel_px,
        closing_kernel_px: s.closing_kernel_px,
        max_candidates: s.max_candidates,
        lock_search_radius_factor: s.lock_search_radius_factor,
    }
}

/// Python `max(0.01, prefs.audio_gain)`, which also maps NaN to 0.01.
pub fn effective_gain(prefs: &Preferences) -> f64 {
    if prefs.audio_gain > 0.01 {
        prefs.audio_gain
    } else {
        0.01
    }
}

/// The detector threshold is divided by the gain so the meter, which shows
/// the level multiplied by the gain, crosses the threshold line when a shot
/// fires. Block size, sample rate and filter keep their defaults, as in Python.
pub fn shot_detector_settings(prefs: &Preferences) -> ShotDetectorSettings {
    let defaults = ShotDetectorSettings::default();
    ShotDetectorSettings {
        threshold: prefs.shot_threshold / effective_gain(prefs),
        refractory_ms: u32::try_from(prefs.shot_refractory_ms).unwrap_or(defaults.refractory_ms),
        ..defaults
    }
}

pub fn coordinator_settings(prefs: &Preferences) -> ShotCoordinatorSettings {
    ShotCoordinatorSettings {
        pre_shot_ms: i64::from(prefs.pre_shot_ms),
        post_shot_ms: i64::from(prefs.post_shot_ms),
    }
}

pub fn frame_transform(prefs: &Preferences) -> FrameTransform {
    FrameTransform {
        rotation_degrees: prefs.camera_rotation,
        flip_horizontal: prefs.camera_flip_h,
        flip_vertical: prefs.camera_flip_v,
        brightness: prefs.camera_brightness,
        contrast: prefs.camera_contrast,
    }
}

/// Python `SessionManager._score_for`. An unmapped shot, or no face at all,
/// scores the empty string.
pub fn score_for(
    faces: &[TargetFace],
    prefs: &Preferences,
    x_mm: Option<f64>,
    y_mm: Option<f64>,
) -> String {
    let (Some(x), Some(y)) = (x_mm, y_mm) else {
        return String::new();
    };
    let Some(face) = get_face(faces, &prefs.target_face) else {
        return String::new();
    };
    let mut rings: Vec<ScoringRing> = face
        .rings
        .iter()
        .filter_map(|ring| {
            let label = ring.label.as_deref().filter(|l| !l.is_empty())?;
            Some(ScoringRing {
                radius_mm: ring.diameter_mm / 2.0,
                label: label.to_owned(),
            })
        })
        .collect();
    // Python's sort is stable and treats incomparable values as equal.
    rings.sort_by(|a, b| {
        a.radius_mm
            .partial_cmp(&b.radius_mm)
            .unwrap_or(Ordering::Equal)
    });
    score_shot(
        x,
        y,
        &rings,
        &ScoreOptions {
            shot_diameter_mm: prefs.shot_diameter_mm,
            centre: (0.0, 0.0),
            direction: ScoringDirection::from_name(&face.scoring_direction),
        },
    )
}

#[cfg(test)]
mod tests {
    use shottrainer_settings::target_faces::{TargetRing, built_in_faces};

    use super::*;

    fn distinct_stored() -> StoredDetectorSettings {
        StoredDetectorSettings {
            min_radius_px: 1,
            max_radius_px: 2,
            blur_kernel: 3,
            min_circularity: 0.4,
            adaptive_block_size: 5,
            adaptive_offset: 6,
            region_fraction: 0.7,
            lock_radius_px: 8.0,
            lock_boost: 9.0,
            lock_release_after_misses: 10,
            opening_kernel_px: 11,
            closing_kernel_px: 12,
            max_candidates: 13,
            lock_search_radius_factor: 14.0,
        }
    }

    #[test]
    fn detector_settings_map_field_for_field() {
        let stored = distinct_stored();
        let tracking = detector_from_store(&stored);
        assert_eq!(
            (
                tracking.min_radius_px,
                tracking.max_radius_px,
                tracking.blur_kernel,
                tracking.min_circularity,
                tracking.adaptive_block_size,
                tracking.adaptive_offset,
                tracking.region_fraction,
            ),
            (1, 2, 3, 0.4, 5, 6, 0.7)
        );
        assert_eq!(
            (
                tracking.lock_radius_px,
                tracking.lock_boost,
                tracking.lock_release_after_misses,
                tracking.opening_kernel_px,
                tracking.closing_kernel_px,
                tracking.max_candidates,
                tracking.lock_search_radius_factor,
            ),
            (8.0, 9.0, 10, 11, 12, 13, 14.0)
        );
        assert_eq!(detector_to_store(&tracking), stored);
    }

    #[test]
    fn detector_defaults_agree() {
        assert_eq!(
            detector_from_store(&StoredDetectorSettings::default()),
            DetectorSettings::default()
        );
    }

    #[test]
    fn shot_settings_divide_the_threshold_by_the_gain() {
        let prefs = Preferences {
            shot_threshold: 0.5,
            audio_gain: 2.0,
            shot_refractory_ms: 600,
            ..Preferences::default()
        };
        let s = shot_detector_settings(&prefs);
        assert_eq!((s.threshold, s.refractory_ms), (0.25, 600));
        let defaults = ShotDetectorSettings::default();
        assert_eq!(
            (s.block_size, s.sample_rate, s.high_pass_alpha),
            (
                defaults.block_size,
                defaults.sample_rate,
                defaults.high_pass_alpha
            )
        );
    }

    #[test]
    fn gain_is_held_at_one_hundredth() {
        for gain in [0.0, -1.0, 0.01, f64::NAN] {
            let prefs = Preferences {
                audio_gain: gain,
                ..Preferences::default()
            };
            assert_eq!(effective_gain(&prefs), 0.01, "gain {gain}");
        }
    }

    #[test]
    fn a_negative_refractory_period_falls_back_to_the_default() {
        let prefs = Preferences {
            shot_refractory_ms: -5,
            ..Preferences::default()
        };
        assert_eq!(shot_detector_settings(&prefs).refractory_ms, 400);
    }

    #[test]
    fn transform_and_window_come_from_the_preferences() {
        let prefs = Preferences {
            camera_rotation: 90,
            camera_flip_h: true,
            camera_brightness: -20.0,
            camera_contrast: 1.5,
            pre_shot_ms: 2000,
            post_shot_ms: 100,
            ..Preferences::default()
        };
        assert_eq!(
            frame_transform(&prefs),
            FrameTransform {
                rotation_degrees: 90,
                flip_horizontal: true,
                flip_vertical: false,
                brightness: -20.0,
                contrast: 1.5,
            }
        );
        assert_eq!(
            coordinator_settings(&prefs),
            ShotCoordinatorSettings {
                pre_shot_ms: 2000,
                post_shot_ms: 100,
            }
        );
    }

    #[test]
    fn scores_against_the_default_face() {
        let faces = built_in_faces();
        let prefs = Preferences::default();
        let score = |x, y| score_for(&faces, &prefs, x, y);
        assert_eq!(score(Some(0.0), Some(0.0)), "X");
        assert_eq!(score(Some(20.0), Some(0.0)), "7");
        assert_eq!(score(Some(100.0), Some(0.0)), "");
        assert_eq!(score(None, Some(0.0)), "");
        assert_eq!(score(Some(0.0), None), "");
    }

    #[test]
    fn unlabelled_rings_do_not_score_and_no_faces_score_nothing() {
        let face = TargetFace {
            key: "default".into(),
            label: "Test".into(),
            rings: vec![
                TargetRing {
                    diameter_mm: 10.0,
                    label: None,
                },
                TargetRing {
                    diameter_mm: 40.0,
                    label: Some("8".into()),
                },
            ],
            shot_diameter_mm: None,
            face_diameter_mm: None,
            scoring_direction: "inward".into(),
        };
        let prefs = Preferences::default();
        assert_eq!(score_for(&[face], &prefs, Some(0.0), Some(0.0)), "8");
        assert_eq!(score_for(&[], &prefs, Some(0.0), Some(0.0)), "");
    }
}
