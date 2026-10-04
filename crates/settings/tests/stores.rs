use std::path::Path;

use serde_json::Value;
use shottrainer_settings::stores::{
    CameraSelection, DetectorSettings, UiState, ZeroOffset, clear_detector_settings,
    clear_zero_offset, load_camera_selection, load_detector_settings, load_ui_state,
    load_zero_offset, resolve_camera_index, save_camera_selection, save_detector_settings,
    save_ui_state, save_zero_offset,
};
use testkit::load_golden;

fn write_case(path: &Path, case: &Value) {
    let name = case["name"].as_str().unwrap();
    match (case.get("raw"), case.get("hex")) {
        (Some(raw), _) => std::fs::write(path, raw.as_str().unwrap()).unwrap(),
        (_, Some(hex)) => {
            let hex = hex.as_str().unwrap();
            let bytes: Vec<u8> = (0..hex.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
                .collect();
            std::fs::write(path, bytes).unwrap();
        }
        _ => panic!("case {name} has no input"),
    }
}

fn cases(golden: &Value, key: &str) -> Vec<Value> {
    let list = golden[key].as_array().unwrap().clone();
    assert!(!list.is_empty(), "no {key} cases");
    list
}

fn detector_from(v: &Value) -> DetectorSettings {
    let i = |k: &str| v[k].as_i64().unwrap() as i32;
    let f = |k: &str| v[k].as_f64().unwrap();
    DetectorSettings {
        min_radius_px: i("min_radius_px"),
        max_radius_px: i("max_radius_px"),
        blur_kernel: i("blur_kernel"),
        min_circularity: f("min_circularity"),
        adaptive_block_size: i("adaptive_block_size"),
        adaptive_offset: i("adaptive_offset"),
        region_fraction: f("region_fraction"),
        lock_radius_px: f("lock_radius_px"),
        lock_boost: f("lock_boost"),
        lock_release_after_misses: i("lock_release_after_misses"),
        opening_kernel_px: i("opening_kernel_px"),
        closing_kernel_px: i("closing_kernel_px"),
        max_candidates: i("max_candidates"),
        lock_search_radius_factor: f("lock_search_radius_factor"),
    }
}

fn camera_from(v: &Value) -> CameraSelection {
    CameraSelection {
        name: v["name"].as_str().unwrap().to_owned(),
        index: v["index"].as_i64(),
    }
}

fn ui_from(v: &Value) -> UiState {
    UiState {
        window_geometry_b64: v["window_geometry_b64"].as_str().unwrap().to_owned(),
        main_splitter_sizes: v["main_splitter_sizes"]
            .as_array()
            .unwrap()
            .iter()
            .map(|n| n.as_i64().unwrap() as i32)
            .collect(),
    }
}

fn zero_from(v: &Value) -> ZeroOffset {
    let coordinate = |v: &Value| match v.as_str() {
        Some("nan") => f64::NAN,
        Some("inf") => f64::INFINITY,
        Some("-inf") => f64::NEG_INFINITY,
        _ => v.as_f64().unwrap(),
    };
    ZeroOffset {
        x_mm: coordinate(&v[0]),
        y_mm: coordinate(&v[1]),
    }
}

#[test]
fn detector_defaults_match_python() {
    let golden = load_golden("stores");
    assert_eq!(
        DetectorSettings::default(),
        detector_from(&golden["detector_defaults"])
    );
}

#[test]
fn detector_load_cases_match_python() {
    let golden = load_golden("stores");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("detector.json");
    for case in cases(&golden, "detector") {
        write_case(&path, &case);
        let expected = (!case["expected"].is_null()).then(|| detector_from(&case["expected"]));
        assert_eq!(load_detector_settings(&path), expected, "{}", case["name"]);
    }
}

#[test]
fn detector_save_matches_python_text() {
    let golden = load_golden("stores");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("nested").join("detector.json");
    for case in cases(&golden, "detector_saves") {
        let value = detector_from(&case["value"]);
        save_detector_settings(&value, &path).unwrap();
        let text = std::fs::read_to_string(&path).unwrap();
        assert_eq!(text, case["text"].as_str().unwrap());
    }
}

#[test]
fn detector_round_trip_clear_and_bad_paths() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("detector.json");
    let original = DetectorSettings {
        min_radius_px: 8,
        max_radius_px: 300,
        blur_kernel: 7,
        adaptive_block_size: 41,
        adaptive_offset: 8,
        region_fraction: 0.5,
        ..DetectorSettings::default()
    };
    save_detector_settings(&original, &path).unwrap();
    assert_eq!(load_detector_settings(&path), Some(original));
    clear_detector_settings(&path).unwrap();
    assert!(!path.exists());
    clear_detector_settings(&path).unwrap();
    assert_eq!(load_detector_settings(&path), None);
    assert_eq!(load_detector_settings(dir.path()), None);
}

#[test]
fn zero_offset_load_cases_match_python() {
    let golden = load_golden("stores");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("zero.json");
    for case in cases(&golden, "zero") {
        write_case(&path, &case);
        let name = case["name"].to_string();
        match (load_zero_offset(&path), case["expected"].as_array()) {
            (None, None) => {}
            (Some(got), Some(want)) => {
                // Compare bits so a lost sign on zero is caught.
                assert_eq!(
                    got.x_mm.to_bits(),
                    want[0].as_f64().unwrap().to_bits(),
                    "{name}"
                );
                assert_eq!(
                    got.y_mm.to_bits(),
                    want[1].as_f64().unwrap().to_bits(),
                    "{name}"
                );
            }
            (got, want) => panic!("{name}: got {got:?}, Python gave {want:?}"),
        }
    }
}

#[test]
fn zero_offset_save_matches_python_text() {
    let golden = load_golden("stores");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("nested").join("zero.json");
    for case in cases(&golden, "zero_saves") {
        let value = zero_from(&case["value"]);
        save_zero_offset(&value, &path).unwrap();
        match case["text"].as_str() {
            Some(text) => assert_eq!(std::fs::read_to_string(&path).unwrap(), text),
            None => assert!(!path.exists(), "{case}"),
        }
    }
}

#[test]
fn zero_offset_round_trip_clear_and_bad_paths() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("zero.json");
    let original = ZeroOffset {
        x_mm: 1.5,
        y_mm: -2.25,
    };
    save_zero_offset(&original, &path).unwrap();
    assert_eq!(load_zero_offset(&path), Some(original));
    save_zero_offset(
        &ZeroOffset {
            x_mm: -0.0,
            y_mm: 0.0,
        },
        &path,
    )
    .unwrap();
    assert!(!path.exists(), "a zero offset removes the file");
    save_zero_offset(&original, &path).unwrap();
    clear_zero_offset(&path).unwrap();
    assert!(!path.exists());
    clear_zero_offset(&path).unwrap();
    assert_eq!(load_zero_offset(&path), None);
    assert_eq!(load_zero_offset(dir.path()), None);
}

#[test]
fn camera_load_cases_match_python() {
    let golden = load_golden("stores");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("camera.json");
    for case in cases(&golden, "camera") {
        write_case(&path, &case);
        assert_eq!(
            load_camera_selection(&path),
            camera_from(&case["expected"]),
            "{}",
            case["name"]
        );
    }
}

#[test]
fn camera_save_matches_python_text() {
    let golden = load_golden("stores");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("nested").join("camera.json");
    for case in cases(&golden, "camera_saves") {
        save_camera_selection(&camera_from(&case["value"]), &path).unwrap();
        let text = std::fs::read_to_string(&path).unwrap();
        assert_eq!(text, case["text"].as_str().unwrap());
    }
}

#[test]
fn camera_documents_that_are_not_objects_give_the_default() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("camera.json");
    for text in ["null", "[]", "3", "\"x\"", "true", "[1, 2"] {
        std::fs::write(&path, text).unwrap();
        assert_eq!(load_camera_selection(&path), CameraSelection::default());
    }
}

#[test]
fn camera_round_trip_and_bad_paths() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("camera.json");
    for original in [
        CameraSelection {
            name: "USB Cam".into(),
            index: Some(2),
        },
        CameraSelection {
            name: String::new(),
            index: None,
        },
    ] {
        save_camera_selection(&original, &path).unwrap();
        assert_eq!(load_camera_selection(&path), original);
    }
    assert_eq!(
        load_camera_selection(&dir.path().join("nope.json")),
        CameraSelection::default()
    );
    assert_eq!(
        load_camera_selection(dir.path()),
        CameraSelection::default()
    );
}

#[test]
fn resolve_camera_index_matches_python() {
    let golden = load_golden("stores");
    for case in cases(&golden, "resolve") {
        let selection = CameraSelection {
            name: case["name"].as_str().unwrap().to_owned(),
            index: case["index"].as_i64(),
        };
        let available: Vec<(i64, String)> = case["available"]
            .as_array()
            .unwrap()
            .iter()
            .map(|a| (a[0].as_i64().unwrap(), a[1].as_str().unwrap().to_owned()))
            .collect();
        assert_eq!(
            resolve_camera_index(&selection, &available),
            case["result"].as_i64().unwrap(),
            "{case}"
        );
    }
}

#[test]
fn ui_state_load_cases_match_python() {
    let golden = load_golden("stores");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("ui_state.json");
    for case in cases(&golden, "ui") {
        write_case(&path, &case);
        assert_eq!(
            load_ui_state(&path),
            ui_from(&case["expected"]),
            "{}",
            case["name"]
        );
    }
}

#[test]
fn ui_state_save_matches_python_text() {
    let golden = load_golden("stores");
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("nested").join("ui_state.json");
    for case in cases(&golden, "ui_saves") {
        save_ui_state(&ui_from(&case["value"]), &path).unwrap();
        let text = std::fs::read_to_string(&path).unwrap();
        assert_eq!(text, case["text"].as_str().unwrap());
    }
}

#[test]
fn ui_state_round_trip_and_bad_paths() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("ui_state.json");
    let original = UiState {
        window_geometry_b64: "AdnQywADAAAAAAAA/w==".into(),
        main_splitter_sizes: vec![200, 400],
    };
    save_ui_state(&original, &path).unwrap();
    assert_eq!(load_ui_state(&path), original);
    assert_eq!(
        load_ui_state(&dir.path().join("nope.json")),
        UiState::default()
    );
    assert_eq!(load_ui_state(dir.path()), UiState::default());
}

#[test]
fn saving_to_a_directory_fails_without_panicking() {
    let dir = tempfile::tempdir().unwrap();
    assert!(save_ui_state(&UiState::default(), dir.path()).is_err());
    assert!(save_camera_selection(&CameraSelection::default(), dir.path()).is_err());
    assert!(save_detector_settings(&DetectorSettings::default(), dir.path()).is_err());
}
