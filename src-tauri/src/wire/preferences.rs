//! The preferences in the webview's camelCase form. `settings.json` keeps
//! Python's snake_case keys, so the settings crate's `Serialize` cannot be
//! reused.

use serde::{Deserialize, Serialize};
use shottrainer_settings::Preferences;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct WirePreferences {
    pub camera_id: Option<i32>,
    pub camera_rotation: i32,
    pub camera_flip_h: bool,
    pub camera_flip_v: bool,
    pub camera_brightness: f64,
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

impl From<&Preferences> for WirePreferences {
    fn from(p: &Preferences) -> Self {
        WirePreferences {
            camera_id: p.camera_id,
            camera_rotation: p.camera_rotation,
            camera_flip_h: p.camera_flip_h,
            camera_flip_v: p.camera_flip_v,
            camera_brightness: p.camera_brightness,
            camera_contrast: p.camera_contrast,
            audio_device: p.audio_device.clone(),
            audio_gain: p.audio_gain,
            shot_threshold: p.shot_threshold,
            shot_refractory_ms: p.shot_refractory_ms,
            pre_shot_ms: p.pre_shot_ms,
            post_shot_ms: p.post_shot_ms,
            release_window_ms: p.release_window_ms,
            target_face: p.target_face.clone(),
            shot_diameter_mm: p.shot_diameter_mm,
            tracking_region_fraction: p.tracking_region_fraction,
            circle_diameter_mm: p.circle_diameter_mm,
            invert_trace_horizontal: p.invert_trace_horizontal,
            invert_trace_vertical: p.invert_trace_vertical,
            show_hold_zone: p.show_hold_zone,
        }
    }
}

impl From<WirePreferences> for Preferences {
    fn from(w: WirePreferences) -> Self {
        Preferences {
            camera_id: w.camera_id,
            camera_rotation: w.camera_rotation,
            camera_flip_h: w.camera_flip_h,
            camera_flip_v: w.camera_flip_v,
            camera_brightness: w.camera_brightness,
            camera_contrast: w.camera_contrast,
            audio_device: w.audio_device,
            audio_gain: w.audio_gain,
            shot_threshold: w.shot_threshold,
            shot_refractory_ms: w.shot_refractory_ms,
            pre_shot_ms: w.pre_shot_ms,
            post_shot_ms: w.post_shot_ms,
            release_window_ms: w.release_window_ms,
            target_face: w.target_face,
            shot_diameter_mm: w.shot_diameter_mm,
            tracking_region_fraction: w.tracking_region_fraction,
            circle_diameter_mm: w.circle_diameter_mm,
            invert_trace_horizontal: w.invert_trace_horizontal,
            invert_trace_vertical: w.invert_trace_vertical,
            show_hold_zone: w.show_hold_zone,
        }
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use serde_json::{Value, json};

    use super::*;

    /// Every field differs from its default and from its neighbours, so a
    /// field mapped to the wrong place changes the round trip.
    pub(crate) fn distinct_preferences() -> Preferences {
        Preferences {
            camera_id: Some(3),
            camera_rotation: 270,
            camera_flip_h: true,
            camera_flip_v: false,
            camera_brightness: -12.5,
            camera_contrast: 1.75,
            audio_device: "USB mic".into(),
            audio_gain: 2.5,
            shot_threshold: 0.4,
            shot_refractory_ms: 450,
            pre_shot_ms: 1200,
            post_shot_ms: 600,
            release_window_ms: 350,
            target_face: "air_rifle_10m".into(),
            shot_diameter_mm: 4.5,
            tracking_region_fraction: 0.6,
            circle_diameter_mm: 42.0,
            invert_trace_horizontal: false,
            invert_trace_vertical: true,
            show_hold_zone: false,
        }
    }

    #[test]
    fn preferences_survive_a_round_trip_through_json() {
        let prefs = distinct_preferences();
        let text = serde_json::to_string(&WirePreferences::from(&prefs)).unwrap();
        let back: WirePreferences = serde_json::from_str(&text).unwrap();
        assert_eq!(Preferences::from(back), prefs);
    }

    #[test]
    fn preferences_use_camel_case_keys() {
        let value = serde_json::to_value(WirePreferences::from(&distinct_preferences())).unwrap();
        let object = value.as_object().unwrap();
        assert_eq!(object.len(), 20);
        assert_eq!(object["cameraId"], json!(3));
        assert_eq!(object["shotRefractoryMs"], json!(450));
        assert_eq!(object["releaseWindowMs"], json!(350));
        assert_eq!(object["invertTraceVertical"], json!(true));
    }

    #[test]
    fn no_camera_is_null() {
        let prefs = Preferences {
            camera_id: None,
            ..Preferences::default()
        };
        let value = serde_json::to_value(WirePreferences::from(&prefs)).unwrap();
        assert_eq!(value["cameraId"], Value::Null);
    }

    #[test]
    fn preferences_with_a_misspelt_key_are_refused() {
        let mut value =
            serde_json::to_value(WirePreferences::from(&Preferences::default())).unwrap();
        let object = value.as_object_mut().unwrap();
        let id = object.remove("cameraId").unwrap();
        object.insert("camera_id".into(), id);
        assert!(serde_json::from_value::<WirePreferences>(value).is_err());
    }
}
