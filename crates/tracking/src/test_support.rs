//! Decoders shared by the tests that read the tracking golden fixtures.

use serde_json::Value;

use crate::detector::DetectorSettings;
use crate::frame::{Frame, PixelFormat};
use crate::models::Detection;

pub fn f64_at(v: &Value, key: &str) -> f64 {
    v[key]
        .as_f64()
        .unwrap_or_else(|| panic!("{key} is not a number in {v}"))
}

pub fn frame_from_json(v: &Value) -> Frame {
    let format = match v["channels"].as_u64() {
        Some(1) => PixelFormat::Grey,
        Some(3) => PixelFormat::Bgr,
        other => panic!("unexpected channel count {other:?}"),
    };
    let data = v["data"]
        .as_array()
        .unwrap()
        .iter()
        .map(|b| u8::try_from(b.as_u64().unwrap()).unwrap())
        .collect();
    let dim = |key: &str| u32::try_from(v[key].as_u64().unwrap()).unwrap();
    Frame::new(dim("width"), dim("height"), format, data).unwrap()
}

pub fn detection_from_json(v: &Value) -> Detection {
    Detection {
        found: v["found"].as_bool().unwrap(),
        x_px: f64_at(v, "x_px"),
        y_px: f64_at(v, "y_px"),
        radius_px: f64_at(v, "radius_px"),
        confidence: f64_at(v, "confidence"),
        rejected_outside_region: v["rejected_outside_region"].as_bool().unwrap(),
        semi_major_px: f64_at(v, "semi_major_px"),
        semi_minor_px: f64_at(v, "semi_minor_px"),
        angle_degrees: f64_at(v, "angle_degrees"),
    }
}

/// Applies the keys present in `v` over the defaults. An unknown key panics
/// so a misspelt fixture key cannot pass silently.
pub fn settings_from_json(v: &Value) -> DetectorSettings {
    let mut s = DetectorSettings::default();
    for (key, value) in v.as_object().unwrap() {
        let int = || i32::try_from(value.as_i64().unwrap()).unwrap();
        let float = || value.as_f64().unwrap();
        match key.as_str() {
            "min_radius_px" => s.min_radius_px = int(),
            "max_radius_px" => s.max_radius_px = int(),
            "blur_kernel" => s.blur_kernel = int(),
            "min_circularity" => s.min_circularity = float(),
            "adaptive_block_size" => s.adaptive_block_size = int(),
            "adaptive_offset" => s.adaptive_offset = int(),
            "region_fraction" => s.region_fraction = float(),
            "lock_radius_px" => s.lock_radius_px = float(),
            "lock_boost" => s.lock_boost = float(),
            "lock_release_after_misses" => s.lock_release_after_misses = int(),
            "opening_kernel_px" => s.opening_kernel_px = int(),
            "closing_kernel_px" => s.closing_kernel_px = int(),
            "max_candidates" => s.max_candidates = int(),
            "lock_search_radius_factor" => s.lock_search_radius_factor = float(),
            other => panic!("unknown detector setting {other}"),
        }
    }
    s
}

/// Flags exactly, every float within the `testkit` tolerance.
#[cfg(feature = "opencv")]
pub fn assert_detection_close(got: &Detection, expected: &Value, context: &str) {
    use testkit::assert_close;

    let want = detection_from_json(expected);
    assert_eq!(got.found, want.found, "{context}: found");
    assert_eq!(
        got.rejected_outside_region, want.rejected_outside_region,
        "{context}: rejected_outside_region"
    );
    for (actual, wanted, name) in [
        (got.x_px, want.x_px, "x_px"),
        (got.y_px, want.y_px, "y_px"),
        (got.radius_px, want.radius_px, "radius_px"),
        (got.confidence, want.confidence, "confidence"),
        (got.semi_major_px, want.semi_major_px, "semi_major_px"),
        (got.semi_minor_px, want.semi_minor_px, "semi_minor_px"),
        (got.angle_degrees, want.angle_degrees, "angle_degrees"),
    ] {
        assert_close(actual, wanted, &format!("{context}: {name}"));
    }
}

/// Decodes a PNG from `testdata/frames/detector` exactly as it was written.
#[cfg(feature = "opencv")]
pub fn load_png_frame(name: &str) -> Frame {
    use opencv::imgcodecs;
    use opencv::prelude::*;

    let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/frames/detector")
        .join(format!("{name}.png"));
    let mat = imgcodecs::imread(path.to_str().unwrap(), imgcodecs::IMREAD_UNCHANGED)
        .unwrap_or_else(|e| panic!("cannot read {path:?}: {e}"));
    assert!(!mat.empty(), "cannot decode {path:?}");
    crate::cv::mat::mat_to_frame(&mat).unwrap()
}
