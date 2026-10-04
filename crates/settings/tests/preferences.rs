use std::path::PathBuf;

use serde_json::Value;
use shottrainer_settings::{
    Platform, Preferences, data_dir_for, load_preferences, save_preferences,
};
use testkit::{assert_close, load_golden};

fn expect(prefs: &Preferences, expected: &Value, context: &str) {
    let e = |k: &str| &expected[k];
    assert_eq!(
        prefs.camera_id,
        e("camera_id").as_i64().map(|v| v as i32),
        "{context} camera_id"
    );
    assert_eq!(
        i64::from(prefs.camera_rotation),
        e("camera_rotation").as_i64().unwrap(),
        "{context}"
    );
    assert_eq!(
        prefs.camera_flip_h,
        e("camera_flip_h").as_bool().unwrap(),
        "{context}"
    );
    assert_eq!(
        prefs.camera_flip_v,
        e("camera_flip_v").as_bool().unwrap(),
        "{context}"
    );
    assert_eq!(
        prefs.audio_device,
        e("audio_device").as_str().unwrap(),
        "{context}"
    );
    assert_eq!(
        prefs.target_face,
        e("target_face").as_str().unwrap(),
        "{context}"
    );
    assert_eq!(
        prefs.invert_trace_horizontal,
        e("invert_trace_horizontal").as_bool().unwrap()
    );
    assert_eq!(
        prefs.invert_trace_vertical,
        e("invert_trace_vertical").as_bool().unwrap()
    );
    assert_eq!(
        prefs.show_hold_zone,
        e("show_hold_zone").as_bool().unwrap(),
        "{context}"
    );
    for (name, actual) in [
        ("shot_refractory_ms", prefs.shot_refractory_ms),
        ("pre_shot_ms", prefs.pre_shot_ms),
        ("post_shot_ms", prefs.post_shot_ms),
        ("release_window_ms", prefs.release_window_ms),
    ] {
        assert_eq!(
            i64::from(actual),
            e(name).as_i64().unwrap(),
            "{context} {name}"
        );
    }
    for (name, actual) in [
        ("camera_brightness", prefs.camera_brightness),
        ("camera_contrast", prefs.camera_contrast),
        ("audio_gain", prefs.audio_gain),
        ("shot_threshold", prefs.shot_threshold),
        ("shot_diameter_mm", prefs.shot_diameter_mm),
        ("tracking_region_fraction", prefs.tracking_region_fraction),
        ("circle_diameter_mm", prefs.circle_diameter_mm),
    ] {
        assert_close(
            actual,
            e(name).as_f64().unwrap(),
            &format!("{context} {name}"),
        );
    }
}

#[test]
fn defaults_match_python() {
    expect(
        &Preferences::default(),
        &load_golden("preferences")["defaults"],
        "defaults",
    );
}

#[test]
fn load_cases_match_python() {
    let golden = load_golden("preferences");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("settings.json");
    for case in golden["cases"].as_array().unwrap() {
        let name = case["name"].as_str().unwrap();
        match (case.get("raw"), case.get("hex")) {
            (Some(raw), _) => std::fs::write(&path, raw.as_str().unwrap()).unwrap(),
            (_, Some(hex)) => {
                let hex = hex.as_str().unwrap();
                let bytes: Vec<u8> = (0..hex.len())
                    .step_by(2)
                    .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
                    .collect();
                std::fs::write(&path, bytes).unwrap();
            }
            _ => panic!("case {name} has no input"),
        }
        expect(&load_preferences(&path), &case["prefs"], name);
    }
}

#[test]
fn save_matches_python_text() {
    let golden = load_golden("preferences");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("nested").join("settings.json");
    for (i, case) in golden["saves"].as_array().unwrap().iter().enumerate() {
        let prefs = prefs_from_golden(&case["prefs"]);
        save_preferences(&prefs, &path).unwrap();
        let text = std::fs::read_to_string(&path).unwrap();
        assert_eq!(text, case["text"].as_str().unwrap(), "save case {i}");
    }
}

// Some save cases hold values the loader rejects (out of range), so build
// the struct directly.
fn prefs_from_golden(v: &Value) -> Preferences {
    let f = |k: &str| v[k].as_f64().unwrap();
    let i = |k: &str| v[k].as_i64().unwrap() as i32;
    let b = |k: &str| v[k].as_bool().unwrap();
    let s = |k: &str| v[k].as_str().unwrap().to_owned();
    Preferences {
        camera_id: v["camera_id"].as_i64().map(|x| x as i32),
        camera_rotation: i("camera_rotation"),
        camera_flip_h: b("camera_flip_h"),
        camera_flip_v: b("camera_flip_v"),
        camera_brightness: f("camera_brightness"),
        camera_contrast: f("camera_contrast"),
        audio_device: s("audio_device"),
        audio_gain: f("audio_gain"),
        shot_threshold: f("shot_threshold"),
        shot_refractory_ms: i("shot_refractory_ms"),
        pre_shot_ms: i("pre_shot_ms"),
        post_shot_ms: i("post_shot_ms"),
        release_window_ms: i("release_window_ms"),
        target_face: s("target_face"),
        shot_diameter_mm: f("shot_diameter_mm"),
        tracking_region_fraction: f("tracking_region_fraction"),
        circle_diameter_mm: f("circle_diameter_mm"),
        invert_trace_horizontal: b("invert_trace_horizontal"),
        invert_trace_vertical: b("invert_trace_vertical"),
        show_hold_zone: b("show_hold_zone"),
    }
}

#[test]
fn negative_zero_brightness_keeps_its_sign_when_saved() {
    let prefs = Preferences {
        camera_brightness: -0.0,
        ..Preferences::default()
    };
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("s.json");
    save_preferences(&prefs, &path).unwrap();
    assert!(
        std::fs::read_to_string(&path)
            .unwrap()
            .contains("\"camera_brightness\": -0.0")
    );
}

#[test]
fn roundtrip() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("s.json");
    let original = Preferences {
        camera_id: Some(2),
        audio_device: "USB Mic".into(),
        shot_threshold: 0.4,
        shot_refractory_ms: 500,
        ..Preferences::default()
    };
    save_preferences(&original, &path).unwrap();
    assert_eq!(load_preferences(&path), original);
}

#[test]
fn missing_path_and_directory_give_defaults() {
    let dir = tempfile::tempdir().unwrap();
    assert_eq!(
        load_preferences(&dir.path().join("nope.json")),
        Preferences::default()
    );
    assert_eq!(load_preferences(dir.path()), Preferences::default());
}

#[test]
fn data_dirs_match_python() {
    let golden = load_golden("preferences");
    for case in golden["data_dirs"].as_array().unwrap() {
        let platform = match case["platform"].as_str().unwrap() {
            "windows" => Platform::Windows,
            "macos" => Platform::MacOs,
            _ => Platform::Linux,
        };
        let env = case["env"].as_object().unwrap().clone();
        let lookup = move |k: &str| env.get(k).and_then(|v| v.as_str()).map(str::to_owned);
        let home = PathBuf::from(case["home"].as_str().unwrap());
        let got = data_dir_for(platform, &lookup, &home);
        assert_eq!(got, PathBuf::from(case["path"].as_str().unwrap()), "{case}");
    }
}
