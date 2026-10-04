//! The catalogue of selectable target faces.
//!
//! Built-in faces are embedded JSON files. The user can add their own to
//! `custom_target_faces.json` in the data directory, a JSON object of faces
//! keyed by id. A custom face shadows a built-in with the same key. Loaders
//! are pure, so the caller decides when to reload and where to cache.

use std::path::{Path, PathBuf};

use serde_json::{Map, Value};

use crate::json_values::replace_non_finite;
use crate::json_values::{parse_python_finite_float, python_str, read_json_object};
use crate::paths::data_dir;

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

/// The on-disk path for user-defined custom faces.
pub fn custom_faces_path() -> PathBuf {
    data_dir().join("custom_target_faces.json")
}

/// Python truthiness of a decoded JSON value, as used by `value or default`.
fn is_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_none_or(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// `str(body.get(field) or default)`.
fn label_or(body: &Map<String, Value>, field: &str, default: &str) -> String {
    match body.get(field) {
        Some(value) if is_truthy(value) => python_str(value),
        _ => default.to_owned(),
    }
}

/// `float(body[field])` kept only when it is finite and positive. Booleans and
/// null are rejected, strings follow Python's `float()` and anything that is
/// not a number or string is rejected.
fn optional_positive_float(body: &Map<String, Value>, field: &str) -> Option<f64> {
    let value = match body.get(field)? {
        Value::Number(n) => n.as_f64()?,
        Value::String(s) => parse_python_finite_float(s)?,
        _ => return None,
    };
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
            let raw = match serde_json::from_str::<Value>(&replace_non_finite(text)) {
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

/// `(key, label)` for every face. `default` comes first and the rest follow by
/// lower-cased label.
pub fn list_target_faces(faces: &[TargetFace]) -> Vec<(String, String)> {
    let mut items: Vec<&TargetFace> = faces.iter().collect();
    items.sort_by_cached_key(|face| (face.key != "default", face.label.to_lowercase()));
    items
        .into_iter()
        .map(|face| (face.key.clone(), face.label.clone()))
        .collect()
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

/// The smallest ring and a mid-sized one, which are worth reporting time-in-ring
/// for. A single ring gives just that ring.
pub fn diagnostic_rings(rings: &[TargetRing]) -> Vec<TargetRing> {
    let mut sorted = rings.to_vec();
    sorted.sort_by(|a, b| a.diameter_mm.total_cmp(&b.diameter_mm));
    match sorted.len() {
        0 => Vec::new(),
        1 => sorted,
        n => vec![sorted[0].clone(), sorted[n / 2].clone()],
    }
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
    fn built_in_catalogue_matches_python() {
        let golden = load_golden("target_faces");
        let expected = &golden["built_in"];
        assert!(!expected.as_array().unwrap().is_empty());
        assert_faces_match(&built_in_faces(), expected, "built-in");
    }

    #[test]
    fn custom_files_match_python() {
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
            let listed: Vec<Vec<String>> = list_target_faces(&merged)
                .into_iter()
                .map(|(k, l)| vec![k, l])
                .collect();
            assert_eq!(json!(listed), case["list"], "{name} list");
            let fallback = get_face(&merged, "nonsense").map(|f| f.key.as_str());
            assert_eq!(fallback, case["fallback"].as_str(), "{name} fallback");
        }
        assert!(loaded_any);
    }

    #[test]
    fn rust_assets_match_the_python_directory() {
        // Removed together with the Python copy of the face files.
        let python = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../src/shottrainer/ui/assets/target_faces");
        let rust = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("assets/target_faces");
        let read = |dir: &std::path::Path| {
            let mut files: Vec<(String, Vec<u8>)> = std::fs::read_dir(dir)
                .unwrap()
                .map(|e| {
                    let e = e.unwrap();
                    (
                        e.file_name().to_string_lossy().into_owned(),
                        std::fs::read(e.path()).unwrap(),
                    )
                })
                .collect();
            files.sort();
            files
        };
        let rust_files = read(&rust);
        assert_eq!(read(&python), rust_files);
        let embedded: Vec<String> = BUILT_IN_SOURCES
            .iter()
            .map(|(stem, _)| format!("{stem}.json"))
            .collect();
        let mut on_disk: Vec<String> = rust_files.into_iter().map(|(n, _)| n).collect();
        on_disk.sort();
        let mut sorted_embedded = embedded.clone();
        sorted_embedded.sort();
        assert_eq!(sorted_embedded, on_disk);
        for (stem, text) in BUILT_IN_SOURCES {
            let bytes = std::fs::read(rust.join(format!("{stem}.json"))).unwrap();
            assert_eq!(text.as_bytes(), bytes.as_slice(), "{stem}");
        }
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
    fn diagnostic_rings_picks_inner_and_mid() {
        let ring = |d: f64, l: &str| TargetRing {
            diameter_mm: d,
            label: Some(l.to_owned()),
        };
        let rings = [
            ring(60.0, "outer"),
            ring(30.0, "mid"),
            ring(10.0, "inner"),
            ring(2.0, "x"),
        ];
        let chosen = diagnostic_rings(&rings);
        assert_eq!(chosen, vec![ring(2.0, "x"), ring(30.0, "mid")]);
        assert_eq!(diagnostic_rings(&rings[..1]), vec![ring(60.0, "outer")]);
        assert!(diagnostic_rings(&[]).is_empty());
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
    fn huge_integer_dimension_in_a_file_is_discarded() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("c.json");
        let huge = "1".repeat(400);
        std::fs::write(
            &path,
            format!(r#"{{"c": {{"shot_diameter_mm": {huge}, "rings": [{{"diameter_mm": 5}}]}}}}"#),
        )
        .unwrap();
        let faces = load_custom_faces(&path);
        assert_eq!(faces.len(), 1);
        assert_eq!(faces[0].shot_diameter_mm, None);
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
