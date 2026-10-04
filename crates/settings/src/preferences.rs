use std::io::Write;
use std::path::Path;

use serde::Serialize;
use serde_json::Value;

use crate::error::SettingsError;
use crate::json_values::{
    read_bool, read_f64_in, read_i32_choice, read_i32_in, read_string, replace_non_finite,
};

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
    if !path.exists() {
        return Preferences::default();
    }
    let text = match std::fs::read_to_string(path) {
        Ok(text) => text,
        Err(err) => {
            log::warn!("Could not read {}: {err}. Using defaults", path.display());
            return Preferences::default();
        }
    };
    let parsed = serde_json::from_str::<Value>(&replace_non_finite(&text));
    let raw = match parsed {
        Ok(Value::Object(map)) => map,
        Ok(_) => {
            log::warn!("Settings file must contain a JSON object. Using defaults");
            return Preferences::default();
        }
        Err(err) => {
            log::warn!("Could not read {}: {err}. Using defaults", path.display());
            return Preferences::default();
        }
    };

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
    let parent = match path.parent() {
        Some(p) if !p.as_os_str().is_empty() => p,
        _ => Path::new("."),
    };
    std::fs::create_dir_all(parent)?;
    let mut buf = Vec::new();
    let mut ser = serde_json::Serializer::with_formatter(&mut buf, PythonFormatter::default());
    prefs.serialize(&mut ser)?;
    let mut tmp = tempfile::NamedTempFile::new_in(parent)?;
    tmp.write_all(&buf)?;
    tmp.persist(path).map_err(|e| e.error)?;
    Ok(())
}

/// Pretty printing with two-space indent plus Python's `ensure_ascii` string
/// escaping and `repr` float formatting.
#[derive(Default)]
struct PythonFormatter {
    inner: serde_json::ser::PrettyFormatter<'static>,
}

macro_rules! delegate {
    ($($name:ident($($arg:ident: $ty:ty),*)),* $(,)?) => {
        $(fn $name<W: ?Sized + Write>(&mut self, w: &mut W $(, $arg: $ty)*) -> std::io::Result<()> {
            self.inner.$name(w $(, $arg)*)
        })*
    };
}

impl serde_json::ser::Formatter for PythonFormatter {
    delegate!(
        begin_array(),
        end_array(),
        begin_array_value(first: bool),
        end_array_value(),
        begin_object(),
        end_object(),
        begin_object_key(first: bool),
        end_object_key(),
        begin_object_value(),
        end_object_value(),
    );

    fn write_string_fragment<W: ?Sized + Write>(
        &mut self,
        w: &mut W,
        fragment: &str,
    ) -> std::io::Result<()> {
        let mut units = [0u16; 2];
        for c in fragment.chars() {
            if c <= '~' {
                write!(w, "{c}")?;
            } else {
                for unit in c.encode_utf16(&mut units) {
                    write!(w, "\\u{unit:04x}")?;
                }
            }
        }
        Ok(())
    }

    fn write_f64<W: ?Sized + Write>(&mut self, w: &mut W, value: f64) -> std::io::Result<()> {
        w.write_all(python_float_repr(value).as_bytes())
    }
}

/// `repr(float)` for finite values. Non-finite values are written as `null`
/// because no valid preference holds one.
fn python_float_repr(value: f64) -> String {
    if !value.is_finite() {
        return "null".into();
    }
    // `{:e}` yields the shortest round-trip digits as `d.ddde-N`.
    let sci = format!("{value:e}");
    let (mantissa, exp) = sci.split_once('e').unwrap_or((&sci, "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let (sign, mantissa) = match mantissa.strip_prefix('-') {
        Some(rest) => ("-", rest),
        None => ("", mantissa),
    };
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    if (-4..16).contains(&exp) {
        let point = exp + 1;
        let body = if point <= 0 {
            format!("0.{}{digits}", "0".repeat((-point) as usize))
        } else if digits.len() as i32 <= point {
            format!("{digits}{}.0", "0".repeat((point as usize) - digits.len()))
        } else {
            format!(
                "{}.{}",
                &digits[..point as usize],
                &digits[point as usize..]
            )
        };
        format!("{sign}{body}")
    } else {
        let frac = if digits.len() > 1 {
            format!(".{}", &digits[1..])
        } else {
            String::new()
        };
        let exp_sign = if exp < 0 { '-' } else { '+' };
        format!("{sign}{}{frac}e{exp_sign}{:02}", &digits[..1], exp.abs())
    }
}
