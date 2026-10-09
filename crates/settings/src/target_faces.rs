//! The catalogue of selectable target faces.
//!
//! Built-in faces are embedded JSON files. The user can add their own to
//! `custom_target_faces.json` in the data directory, a JSON object of faces
//! keyed by id. A custom face shadows a built-in with the same key. Loaders
//! are pure, so the caller decides when to reload and where to cache.

use std::path::Path;

use serde_json::{Map, Value};

use crate::json_values::read_json_object;

/// Built-in faces in catalogue order, which is the sorted order of the file
/// names. The key is the file name stem and is stored in preferences and in
/// every session, so entries are never renamed.
const BUILT_IN_SOURCES: [(&str, &str); 6] = [
    (
        "air_rifle_10m",
        include_str!("../assets/target_faces/air_rifle_10m.json"),
    ),
    (
        "default",
        include_str!("../assets/target_faces/default.json"),
    ),
    (
        "nsra_100yd_prone_rifle_1001c_199618",
        include_str!("../assets/target_faces/nsra_100yd_prone_rifle_1001c_199618.json"),
    ),
    (
        "nsra_25yd_prone_rifle_2510_BM8918",
        include_str!("../assets/target_faces/nsra_25yd_prone_rifle_2510_BM8918.json"),
    ),
    (
        "nsra_50m_prone_rifle_mm12c_199618",
        include_str!("../assets/target_faces/nsra_50m_prone_rifle_mm12c_199618.json"),
    ),
    (
        "smallbore_50m",
        include_str!("../assets/target_faces/smallbore_50m.json"),
    ),
];

/// A single scoring ring. `diameter_mm` is the full printed width.
#[derive(Debug, Clone, PartialEq)]
pub struct TargetRing {
    pub diameter_mm: f64,
    pub label: Option<String>,
}

/// A target face and its metadata. `scoring_direction` is `"inward"` or
/// `"outward"`.
#[derive(Debug, Clone, PartialEq)]
pub struct TargetFace {
    pub key: String,
    pub label: String,
    pub rings: Vec<TargetRing>,
    pub shot_diameter_mm: Option<f64>,
    pub face_diameter_mm: Option<f64>,
    pub scoring_direction: String,
}

/// A non-empty string field, otherwise `default`.
fn label_or(body: &Map<String, Value>, field: &str, default: &str) -> String {
    match body.get(field).and_then(Value::as_str) {
        Some(label) if !label.is_empty() => label.to_owned(),
        _ => default.to_owned(),
    }
}

/// A JSON number kept only when it is finite and positive.
fn optional_positive_float(body: &Map<String, Value>, field: &str) -> Option<f64> {
    let value = body.get(field)?.as_f64()?;
    (value.is_finite() && value > 0.0).then_some(value)
}

/// Entries without a positive, finite `diameter_mm` are skipped.
fn parse_rings(rings_raw: &[Value]) -> Vec<TargetRing> {
    rings_raw
        .iter()
        .filter_map(|entry| {
            let ring = entry.as_object()?;
            let diameter_mm = optional_positive_float(ring, "diameter_mm")?;
            Some(TargetRing {
                diameter_mm,
                label: Some(label_or(ring, "label", "")),
            })
        })
        .collect()
}

/// Builds a face from a JSON body, or `None` when the body is not an object,
/// `rings` is not a list or no ring is valid. Other invalid fields fall back to
/// their defaults.
fn parse_face(body: &Value, key: &str) -> Option<TargetFace> {
    let body = body.as_object()?;
    let rings = match body.get("rings") {
        None => Vec::new(),
        Some(Value::Array(items)) => parse_rings(items),
        Some(_) => return None,
    };
    if rings.is_empty() {
        return None;
    }
    let scoring_direction = match body.get("scoring_direction").and_then(Value::as_str) {
        Some(direction @ ("inward" | "outward")) => direction.to_owned(),
        _ => "inward".to_owned(),
    };
    Some(TargetFace {
        key: key.to_owned(),
        label: label_or(body, "label", key),
        rings,
        shot_diameter_mm: optional_positive_float(body, "shot_diameter_mm"),
        face_diameter_mm: optional_positive_float(body, "face_diameter_mm"),
        scoring_direction,
    })
}

/// The embedded faces in catalogue order.
pub fn built_in_faces() -> Vec<TargetFace> {
    BUILT_IN_SOURCES
        .iter()
        .filter_map(|(key, text)| {
            let raw = match serde_json::from_str::<Value>(text) {
                Ok(raw) => raw,
                Err(err) => {
                    log::warn!("Could not read built-in face {key}: {err}");
                    return None;
                }
            };
            parse_face(&raw, key)
        })
        .collect()
}

/// Reads the user's custom faces in file order. A missing, unreadable or
/// malformed file, or one that is not a JSON object, gives no faces. Each
/// invalid face is dropped on its own. When a key repeats, the last body wins
/// at the position of the first.
pub fn load_custom_faces(path: &Path) -> Vec<TargetFace> {
    let Some(raw) = read_json_object(path, "Custom target faces") else {
        return Vec::new();
    };
    raw.iter()
        .filter_map(|(key, body)| parse_face(body, key))
        .collect()
}

/// Built-ins followed by custom faces. A custom face replaces a built-in with
/// the same key in place, so the catalogue order stays stable.
pub fn merged_faces(built_in: &[TargetFace], custom: &[TargetFace]) -> Vec<TargetFace> {
    let mut merged = built_in.to_vec();
    for face in custom {
        match merged.iter_mut().find(|existing| existing.key == face.key) {
            Some(slot) => *slot = face.clone(),
            None => merged.push(face.clone()),
        }
    }
    merged
}

/// The face for `name`, without any fallback.
pub fn face_for_name<'a>(faces: &'a [TargetFace], name: &str) -> Option<&'a TargetFace> {
    faces.iter().find(|face| face.key == name)
}

/// The face for `name`, falling back to `default` and then the first face.
pub fn get_face<'a>(faces: &'a [TargetFace], name: &str) -> Option<&'a TargetFace> {
    face_for_name(faces, name)
        .or_else(|| face_for_name(faces, "default"))
        .or_else(|| faces.first())
}

/// The rings for `name` with the fallback of [`get_face`], empty when there are
/// no faces.
pub fn rings_for_face<'a>(faces: &'a [TargetFace], name: &str) -> &'a [TargetRing] {
    get_face(faces, name).map_or(&[], |face| face.rings.as_slice())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};
    use testkit::{assert_close, load_golden};

    fn assert_face_matches(face: &TargetFace, expected: &Value, context: &str) {
        assert_eq!(face.key, expected["key"].as_str().unwrap(), "{context} key");
        assert_eq!(
            face.label,
            expected["label"].as_str().unwrap(),
            "{context} label"
        );
        assert_eq!(
            face.scoring_direction,
            expected["scoring_direction"].as_str().unwrap(),
            "{context} direction"
        );
        for (actual, field) in [
            (face.shot_diameter_mm, "shot_diameter_mm"),
            (face.face_diameter_mm, "face_diameter_mm"),
        ] {
            match (actual, expected[field].as_f64()) {
                (Some(a), Some(e)) => assert_close(a, e, &format!("{context} {field}")),
                (None, None) => {}
                (a, e) => panic!("{context} {field}: expected {e:?}, got {a:?}"),
            }
        }
        let rings = expected["rings"].as_array().unwrap();
        assert_eq!(face.rings.len(), rings.len(), "{context} ring count");
        for (i, (ring, want)) in face.rings.iter().zip(rings).enumerate() {
            assert_close(
                ring.diameter_mm,
                want[0].as_f64().unwrap(),
                &format!("{context} ring {i}"),
            );
            assert_eq!(
                ring.label.as_deref(),
                want[1].as_str(),
                "{context} ring {i} label"
            );
        }
    }

    fn assert_faces_match(faces: &[TargetFace], expected: &Value, context: &str) {
        let expected = expected.as_array().unwrap();
        assert_eq!(faces.len(), expected.len(), "{context} face count");
        for (face, want) in faces.iter().zip(expected) {
            assert_face_matches(face, want, context);
        }
    }

    #[test]
    fn built_in_catalogue_matches_the_golden_cases() {
        let golden = load_golden("target_faces");
        let expected = &golden["built_in"];
        assert!(!expected.as_array().unwrap().is_empty());
        assert_faces_match(&built_in_faces(), expected, "built-in");
    }

    #[test]
    fn custom_files_match_the_golden_cases() {
        let golden = load_golden("target_faces");
        let cases = golden["cases"].as_array().unwrap();
        assert!(cases.len() > 20);
        let built_in = built_in_faces();
        let mut loaded_any = false;
        for case in cases {
            let name = case["name"].as_str().unwrap();
            let dir = tempfile::tempdir().unwrap();
            let path = dir.path().join("custom_target_faces.json");
            if case.get("directory").is_some() {
                std::fs::create_dir(&path).unwrap();
            } else if let Some(hex) = case.get("bytes_hex").and_then(Value::as_str) {
                let bytes: Vec<u8> = (0..hex.len())
                    .step_by(2)
                    .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
                    .collect();
                std::fs::write(&path, bytes).unwrap();
            } else if let Some(text) = case["text"].as_str() {
                std::fs::write(&path, text).unwrap();
            }
            let custom = load_custom_faces(&path);
            assert_faces_match(&custom, &case["faces"], name);
            loaded_any |= !custom.is_empty();

            let merged = merged_faces(&built_in, &custom);
            let keys: Vec<&str> = merged.iter().map(|f| f.key.as_str()).collect();
            let want_keys: Vec<&str> = case["merged_keys"]
                .as_array()
                .unwrap()
                .iter()
                .map(|k| k.as_str().unwrap())
                .collect();
            assert_eq!(keys, want_keys, "{name} merged keys");
            let fallback = get_face(&merged, "nonsense").map(|f| f.key.as_str());
            assert_eq!(fallback, case["fallback"].as_str(), "{name} fallback");
        }
        assert!(loaded_any);
    }

    #[test]
    fn embedded_catalogue_covers_assets_and_matches_golden_faces() {
        let rust = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("assets/target_faces");
        let mut on_disk: Vec<String> = std::fs::read_dir(&rust)
            .unwrap()
            .map(|entry| entry.unwrap().file_name().to_string_lossy().into_owned())
            .collect();
        on_disk.sort();
        let mut embedded: Vec<String> = BUILT_IN_SOURCES
            .iter()
            .map(|(stem, _)| format!("{stem}.json"))
            .collect();
        embedded.sort();
        assert_eq!(embedded, on_disk);
        for (stem, text) in BUILT_IN_SOURCES {
            let bytes = std::fs::read(rust.join(format!("{stem}.json"))).unwrap();
            assert_eq!(text.as_bytes(), bytes.as_slice(), "{stem}");
        }
        let golden = load_golden("target_faces");
        assert_faces_match(&built_in_faces(), &golden["built_in"], "embedded catalogue");
    }

    #[test]
    fn built_in_metadata_and_lookup() {
        let faces = built_in_faces();
        let face = face_for_name(&faces, "nsra_50m_prone_rifle_mm12c_199618").unwrap();
        assert_eq!(face.shot_diameter_mm, Some(5.6));
        assert_eq!(face.face_diameter_mm, Some(112.5));
        assert!(face_for_name(&faces, "nonsense").is_none());
        assert_eq!(
            rings_for_face(&faces, "nonsense"),
            rings_for_face(&faces, "default")
        );
        assert!(rings_for_face(&[], "default").is_empty());
        assert!(get_face(&[], "default").is_none());
    }

    #[test]
    fn invalid_custom_dimensions_are_discarded() {
        let values = [json!(0), json!(-1), json!(true), json!(null)];
        for field in ["diameter_mm", "shot_diameter_mm", "face_diameter_mm"] {
            for value in &values {
                let mut body = json!({"rings": [{"diameter_mm": 10.0, "label": "X"}]});
                if field == "diameter_mm" {
                    body["rings"]
                        .as_array_mut()
                        .unwrap()
                        .push(json!({"diameter_mm": value, "label": "1"}));
                } else {
                    body[field] = value.clone();
                }
                let face = parse_face(&body, "custom").unwrap();
                assert_eq!(face.rings.len(), 1, "{field} {value}");
                assert_eq!(face.shot_diameter_mm, None);
                assert_eq!(face.face_diameter_mm, None);
            }
        }
    }

    #[test]
    fn a_number_too_large_for_a_float_makes_the_file_unreadable() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("c.json");
        let huge = "1".repeat(400);
        std::fs::write(
            &path,
            format!(r#"{{"c": {{"shot_diameter_mm": {huge}, "rings": [{{"diameter_mm": 5}}]}}}}"#),
        )
        .unwrap();
        assert!(load_custom_faces(&path).is_empty());
    }

    #[test]
    fn invalid_custom_face_does_not_replace_built_in() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("c.json");
        std::fs::write(&path, r#"{"default": {"rings": [{"diameter_mm": -10}]}}"#).unwrap();
        let built_in = built_in_faces();
        let merged = merged_faces(&built_in, &load_custom_faces(&path));
        assert_eq!(
            face_for_name(&merged, "default"),
            face_for_name(&built_in, "default")
        );
    }
}
