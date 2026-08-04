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
