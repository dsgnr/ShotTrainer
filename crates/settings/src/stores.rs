//! The small JSON state files next to the preferences: detector tuning, the
//! zero offset, the camera selection and the window layout.

use std::path::Path;

use serde::Serialize;
use serde_json::Value;

use crate::error::SettingsError;
use crate::json_values::{
    parse_python_finite_float, parse_python_int, python_str, read_finite_f64, read_i32,
    read_json_object, read_string,
};
use crate::json_write::write_json_atomic;

/// Removes `path`, treating a missing file as success.
fn remove_file_if_present(path: &Path) -> Result<(), SettingsError> {
    match std::fs::remove_file(path) {
        Err(err) if err.kind() != std::io::ErrorKind::NotFound => Err(err.into()),
        _ => Ok(()),
    }
}

/// Detector tuning as stored in `detector_settings.json`. Field order is the
/// order Python writes keys in.
#[derive(Debug, Clone, PartialEq, Serialize)]
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
        Self {
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

impl DetectorSettings {
    /// The checks the Python loader applies after reading every field.
    fn is_usable(&self) -> bool {
        0 < self.min_radius_px
            && self.min_radius_px <= self.max_radius_px
            && self.blur_kernel >= 0
            && !(self.blur_kernel >= 3 && self.blur_kernel % 2 == 0)
            && self.adaptive_block_size >= 3
            && (0.0..=1.0).contains(&self.min_circularity)
            && 0.0 < self.region_fraction
            && self.region_fraction <= 1.0
            && self.lock_radius_px > 0.0
            && self.lock_boost > 0.0
            && self.lock_release_after_misses > 0
            && self.opening_kernel_px >= 0
            && self.closing_kernel_px >= 0
            && self.max_candidates > 0
            && self.lock_search_radius_factor > 0.0
    }
}

/// Reads saved detector settings. `None` means there are none to use, either
/// because the file is missing or because it is malformed or holds an invalid
/// value. Unlike the preferences, one invalid value discards the whole file.
/// Unknown keys are ignored and missing keys keep their defaults.
pub fn load_detector_settings(path: &Path) -> Option<DetectorSettings> {
    let raw = read_json_object(path, "Detector settings")?;
    let mut s = DetectorSettings::default();
    macro_rules! field {
        ($key:literal, $slot:expr, $read:expr) => {
            if let Some(value) = raw.get($key) {
                match $read(value) {
                    Some(v) => $slot = v,
                    None => {
                        log::warn!("Invalid detector setting {}. Using defaults", $key);
                        return None;
                    }
                }
            }
        };
    }
    field!("min_radius_px", s.min_radius_px, read_i32);
    field!("max_radius_px", s.max_radius_px, read_i32);
    field!("blur_kernel", s.blur_kernel, read_i32);
    field!("min_circularity", s.min_circularity, read_finite_f64);
    field!("adaptive_block_size", s.adaptive_block_size, read_i32);
    field!("adaptive_offset", s.adaptive_offset, read_i32);
    field!("region_fraction", s.region_fraction, read_finite_f64);
    field!("lock_radius_px", s.lock_radius_px, read_finite_f64);
    field!("lock_boost", s.lock_boost, read_finite_f64);
    field!(
        "lock_release_after_misses",
        s.lock_release_after_misses,
        read_i32
    );
    field!("opening_kernel_px", s.opening_kernel_px, read_i32);
    field!("closing_kernel_px", s.closing_kernel_px, read_i32);
    field!("max_candidates", s.max_candidates, read_i32);
    field!(
        "lock_search_radius_factor",
        s.lock_search_radius_factor,
        read_finite_f64
    );
    if !s.is_usable() {
        log::warn!("Detector settings are out of range. Using defaults");
        return None;
    }
    Some(s)
}

pub fn save_detector_settings(s: &DetectorSettings, path: &Path) -> Result<(), SettingsError> {
    write_json_atomic(s, path)
}

/// Deletes the detector settings file. A missing file is not an error.
pub fn clear_detector_settings(path: &Path) -> Result<(), SettingsError> {
    remove_file_if_present(path)
}

/// The zero-on-aim offset in millimetres.
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct ZeroOffset {
    pub x_mm: f64,
    pub y_mm: f64,
}

/// A coordinate the way Python's `float()` reads it, except that booleans,
/// non-finite values and values that overflow to infinity are rejected.
/// Strings are converted like `float(str)`, so `"2.5"` is accepted.
fn read_offset_coordinate(value: &Value) -> Option<f64> {
    match value {
        Value::String(text) => parse_python_finite_float(text),
        other => read_finite_f64(other),
    }
}

/// Reads the saved offset. `None` means there is none to apply, because the
/// file is missing, malformed or holds a missing, non-numeric, non-finite or
/// overflowing coordinate. Python treats `None` and `(0, 0)` alike. A file that
/// holds valid zeros loads as `Some`.
pub fn load_zero_offset(path: &Path) -> Option<ZeroOffset> {
    let raw = read_json_object(path, "Zero offset")?;
    let coordinate = |key: &str| raw.get(key).and_then(read_offset_coordinate);
    match (coordinate("x_mm"), coordinate("y_mm")) {
        (Some(x_mm), Some(y_mm)) => Some(ZeroOffset { x_mm, y_mm }),
        _ => {
            log::warn!(
                "Could not read {}: invalid zero offset. Using no offset",
                path.display()
            );
            None
        }
    }
}

/// Saves the offset. An offset of zero on both axes removes the file, as in
/// Python. A non-finite coordinate is written as `null`, which the loader
/// rejects.
pub fn save_zero_offset(z: &ZeroOffset, path: &Path) -> Result<(), SettingsError> {
    if z.x_mm == 0.0 && z.y_mm == 0.0 {
        return clear_zero_offset(path);
    }
    write_json_atomic(z, path)
}

/// Deletes the zero offset file. A missing file is not an error.
pub fn clear_zero_offset(path: &Path) -> Result<(), SettingsError> {
    remove_file_if_present(path)
}

/// The chosen camera. `index` is `None` when no camera is selected.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CameraSelection {
    pub name: String,
    pub index: Option<i64>,
}

impl Default for CameraSelection {
    fn default() -> Self {
        Self {
            name: String::new(),
            index: Some(0),
        }
    }
}

/// Reads the saved camera selection. Like Python, a `name` that is not a string
/// is converted with `str()` and an `index` that is not an integer (a boolean
/// counts as 0 or 1) becomes `None`, including a missing one. A document that
/// is not an object, which makes Python raise, gives the default. Integers
/// beyond `i64` become `None`. A non-finite `name` prints as `[]`.
pub fn load_camera_selection(path: &Path) -> CameraSelection {
    let Some(raw) = read_json_object(path, "Camera selection") else {
        return CameraSelection::default();
    };
    CameraSelection {
        name: raw.get("name").map(python_str).unwrap_or_default(),
        index: match raw.get("index") {
            Some(Value::Bool(b)) => Some(i64::from(*b)),
            Some(Value::Number(n)) => n.as_i64(),
            _ => None,
        },
    }
}

pub fn save_camera_selection(c: &CameraSelection, path: &Path) -> Result<(), SettingsError> {
    write_json_atomic(c, path)
}

/// Picks a device index. Tries a device with the saved name, then the saved
/// index when it is present, then the first device. With no devices it returns
/// the saved index, or 0 when there is none.
pub fn resolve_camera_index(selection: &CameraSelection, available: &[(i64, String)]) -> i64 {
    let Some(first) = available.first() else {
        return selection.index.unwrap_or(0);
    };
    if !selection.name.is_empty()
        && let Some((index, _)) = available.iter().find(|(_, name)| *name == selection.name)
    {
        return *index;
    }
    if let Some(saved) = selection.index
        && available.iter().any(|(index, _)| *index == saved)
    {
        return saved;
    }
    first.0
}

/// The saved window layout. `window_geometry_b64` is an opaque string that is
/// stored and returned unchanged. Python fills it with a base64 Qt blob and the
/// Rust application will use its own key later. Python writes no other keys and
/// drops unknown ones on save, so this does too.
#[derive(Debug, Clone, PartialEq, Default, Serialize)]
pub struct UiState {
    pub window_geometry_b64: String,
    pub main_splitter_sizes: Vec<i32>,
}

/// A splitter size the way Python's loader accepts it. Integers and decimal
/// strings in `0..=i32::MAX` are kept. Booleans, floats and anything else are
/// dropped.
fn read_splitter_size(value: &Value) -> Option<i32> {
    let size = match value {
        Value::Number(n) => i128::from(n.as_i64()?),
        Value::String(text) => parse_python_int(text)?,
        _ => return None,
    };
    i32::try_from(size).ok().filter(|v| *v >= 0)
}

/// Reads the saved layout. A missing or malformed file, or a geometry or sizes
/// value of the wrong type, gives the default. Invalid entries are dropped
/// from the sizes individually.
pub fn load_ui_state(path: &Path) -> UiState {
    let Some(raw) = read_json_object(path, "UI state") else {
        return UiState::default();
    };
    let geometry = match raw.get("window_geometry_b64") {
        None => Some(String::new()),
        Some(value) => read_string(value),
    };
    let sizes = match raw.get("main_splitter_sizes") {
        None => Some(&[][..]),
        Some(Value::Array(items)) => Some(items.as_slice()),
        Some(_) => None,
    };
    match (geometry, sizes) {
        (Some(window_geometry_b64), Some(items)) => UiState {
            window_geometry_b64,
            main_splitter_sizes: items.iter().filter_map(read_splitter_size).collect(),
        },
        _ => UiState::default(),
    }
}

pub fn save_ui_state(u: &UiState, path: &Path) -> Result<(), SettingsError> {
    write_json_atomic(u, path)
}
