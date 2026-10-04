use std::path::Path;

use serde::Serialize;
use serde_json::{Map, Value};

use crate::error::SettingsError;
use crate::json_values::{
    read_bool, read_f64_in, read_i32_choice, read_i32_in, read_json_object, read_string,
};
use crate::json_write::write_json_atomic;

/// Field order is the order Python writes keys in.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Preferences {
    /// `None` means no camera is selected.
    pub camera_id: Option<i32>,
    /// 0, 90, 180 or 270 degrees, clockwise.
    pub camera_rotation: i32,
    pub camera_flip_h: bool,
    pub camera_flip_v: bool,
    /// -100..100 additive offset, 0 = no change.
    pub camera_brightness: f64,
    /// 0.5..2.0 multiplier, 1.0 = no change.
    pub camera_contrast: f64,
    pub audio_device: String,
    pub audio_gain: f64,
    pub shot_threshold: f64,
    pub shot_refractory_ms: i32,
    pub pre_shot_ms: i32,
    pub post_shot_ms: i32,
    pub release_window_ms: i32,
    pub target_face: String,
    pub shot_diameter_mm: f64,
    pub tracking_region_fraction: f64,
    pub circle_diameter_mm: f64,
    pub invert_trace_horizontal: bool,
    pub invert_trace_vertical: bool,
    pub show_hold_zone: bool,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            camera_id: Some(0),
            camera_rotation: 0,
            camera_flip_h: false,
            camera_flip_v: false,
            camera_brightness: 0.0,
            camera_contrast: 1.0,
            audio_device: "default".into(),
            audio_gain: 1.0,
            shot_threshold: 0.25,
            shot_refractory_ms: 400,
            pre_shot_ms: 1500,
            post_shot_ms: 800,
            release_window_ms: 250,
            target_face: "default".into(),
            shot_diameter_mm: 4.5,
            tracking_region_fraction: 0.7,
            circle_diameter_mm: 60.0,
            invert_trace_horizontal: false,
            invert_trace_vertical: false,
            show_hold_zone: true,
        }
    }
}

/// Reads saved preferences. A missing, unreadable or malformed file gives the
/// defaults, and an invalid value falls back on its own without affecting the
/// other keys. Unknown keys are ignored.
pub fn load_preferences(path: &Path) -> Preferences {
    match read_json_object(path, "Settings") {
        Some(raw) => preferences_from_object(&raw),
        None => Preferences::default(),
    }
}

/// Applies the loader's per-key rules to preferences that did not come from
/// the file, such as values sent by the interface. Each invalid or non-finite
/// value is replaced by its default with a warning.
pub fn validate_preferences(prefs: &Preferences) -> Preferences {
    match serde_json::to_value(prefs) {
        Ok(Value::Object(raw)) => preferences_from_object(&raw),
        _ => Preferences::default(),
    }
}

fn preferences_from_object(raw: &Map<String, Value>) -> Preferences {
    let mut prefs = Preferences::default();
    macro_rules! field {
        ($key:literal, $slot:expr, $read:expr) => {
            if let Some(value) = raw.get($key) {
                match $read(value) {
                    Some(v) => $slot = v,
                    None => log::warn!("Invalid preference {}. Using its default", $key),
                }
            }
        };
    }
    match raw.get("camera_id") {
        Some(Value::Null) => prefs.camera_id = None,
        Some(value) => match read_i32_in(value, 0, i32::MAX) {
            Some(v) => prefs.camera_id = Some(v),
            None => log::warn!("Invalid preference camera_id. Using its default"),
        },
        None => {}
    }
    field!("camera_rotation", prefs.camera_rotation, |v| {
        read_i32_choice(v, &[0, 90, 180, 270])
    });
    field!("camera_flip_h", prefs.camera_flip_h, read_bool);
    field!("camera_flip_v", prefs.camera_flip_v, read_bool);
    field!("camera_brightness", prefs.camera_brightness, |v| {
        read_f64_in(v, -100.0, 100.0)
    });
    field!("camera_contrast", prefs.camera_contrast, |v| {
        read_f64_in(v, 0.5, 2.0)
    });
    field!("audio_device", prefs.audio_device, read_string);
    field!("audio_gain", prefs.audio_gain, |v| {
        read_f64_in(v, 0.1, 10.0)
    });
    field!("shot_threshold", prefs.shot_threshold, |v| {
        read_f64_in(v, 0.01, 1.0)
    });
    field!("shot_refractory_ms", prefs.shot_refractory_ms, |v| {
        read_i32_in(v, 50, 5000)
    });
    field!("pre_shot_ms", prefs.pre_shot_ms, |v| {
        read_i32_in(v, 0, 10000)
    });
    field!("post_shot_ms", prefs.post_shot_ms, |v| {
        read_i32_in(v, 0, 10000)
    });
    field!("release_window_ms", prefs.release_window_ms, |v| {
        read_i32_in(v, 50, 2000)
    });
    field!("target_face", prefs.target_face, read_string);
    field!("shot_diameter_mm", prefs.shot_diameter_mm, |v| {
        read_f64_in(v, 0.5, 25.0)
    });
    field!(
        "tracking_region_fraction",
        prefs.tracking_region_fraction,
        |v| read_f64_in(v, 0.1, 1.0)
    );
    field!("circle_diameter_mm", prefs.circle_diameter_mm, |v| {
        read_f64_in(v, 5.0, 1000.0)
    });
    field!(
        "invert_trace_horizontal",
        prefs.invert_trace_horizontal,
        read_bool
    );
    field!(
        "invert_trace_vertical",
        prefs.invert_trace_vertical,
        read_bool
    );
    field!("show_hold_zone", prefs.show_hold_zone, read_bool);
    prefs
}

/// Writes the preferences the way `json.dumps(..., indent=2)` does, through a
/// temporary file in the same directory so a reader never sees a partial file.
pub fn save_preferences(prefs: &Preferences, path: &Path) -> Result<(), SettingsError> {
    write_json_atomic(prefs, path)
}
