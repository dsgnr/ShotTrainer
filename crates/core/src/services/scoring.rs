//! Score a shot from its position and the ring layout.

/// A scoring ring with a radius in millimetres and a label.
#[derive(Debug, Clone, PartialEq)]
pub struct ScoringRing {
    pub radius_mm: f64,
    pub label: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ScoringDirection {
    /// The shot scores the innermost ring it touches.
    #[default]
    Inward,
    /// The shot scores the outermost ring it sits strictly inside.
    Outward,
}

impl ScoringDirection {
    /// Any string other than "outward" means inward, as in the Python code.
    pub fn from_name(name: &str) -> Self {
        if name == "outward" {
            Self::Outward
        } else {
            Self::Inward
        }
    }
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct ScoreOptions {
    pub shot_diameter_mm: f64,
    pub centre: (f64, f64),
    pub direction: ScoringDirection,
}

/// Returns the label of the ring the shot scores, or an empty string for a
/// miss or an empty ring list.
///
/// A shot touches a ring when its outer edge (centre distance minus half the
/// shot diameter) is within the ring radius. Inward scoring walks the rings in
/// the order given and accepts `<=`. Outward scoring walks them by ascending
/// radius and accepts only `<`.
pub fn score_shot(x_mm: f64, y_mm: f64, rings: &[ScoringRing], options: &ScoreOptions) -> String {
    if rings.is_empty() {
        return String::new();
    }
    let distance = (x_mm - options.centre.0).hypot(y_mm - options.centre.1);
    let shot_edge = distance - options.shot_diameter_mm / 2.0;

    match options.direction {
        ScoringDirection::Outward => {
            let mut sorted: Vec<&ScoringRing> = rings.iter().collect();
            sorted.sort_by(|a, b| a.radius_mm.total_cmp(&b.radius_mm));
            sorted
                .into_iter()
                .find(|r| shot_edge < r.radius_mm)
                .map(|r| r.label.clone())
                .unwrap_or_default()
        }
        ScoringDirection::Inward => rings
            .iter()
            .find(|r| shot_edge <= r.radius_mm)
            .map(|r| r.label.clone())
            .unwrap_or_default(),
    }
}

/// Best-effort numeric value for a ring label. `X` scores 10 and anything
/// that does not parse as a number returns `None`.
pub fn label_to_value(label: &str) -> Option<f64> {
    if label.is_empty() {
        return None;
    }
    if label.to_uppercase() == "X" {
        return Some(10.0);
    }
    parse_python_float(label)
}

/// Mirrors Python's `float()` for ASCII input. Surrounding whitespace is
/// ignored and single underscores are allowed between digits. Non-ASCII
/// digits, which Python also accepts, are not supported.
fn parse_python_float(text: &str) -> Option<f64> {
    let text = text.trim();
    if text.contains('_') {
        let chars: Vec<char> = text.chars().collect();
        for (i, c) in chars.iter().enumerate() {
            if *c == '_' {
                let before = i.checked_sub(1).and_then(|j| chars.get(j));
                let after = chars.get(i + 1);
                let digit = |c: Option<&char>| c.is_some_and(|c| c.is_ascii_digit());
                if !digit(before) || !digit(after) {
                    return None;
                }
            }
        }
        return text.replace('_', "").parse().ok();
    }
    text.parse().ok()
}

/// Sums the numeric values of the labels. Labels without a value count as zero.
pub fn total_score<I, S>(scores: I) -> f64
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    scores
        .into_iter()
        .filter_map(|s| label_to_value(s.as_ref()))
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;
    use testkit::{assert_close, load_golden};

    fn ring_list(v: &serde_json::Value) -> Vec<ScoringRing> {
        v.as_array()
            .unwrap()
            .iter()
            .map(|r| ScoringRing {
                radius_mm: r[0].as_f64().unwrap(),
                label: r[1].as_str().unwrap().to_string(),
            })
            .collect()
    }

    #[test]
    fn score_shot_matches_python() {
        let golden = load_golden("scoring");
        let cases = golden["score_shot"].as_array().unwrap();
        assert!(cases.len() > 100);
        for case in cases {
            let options = ScoreOptions {
                shot_diameter_mm: case["shot_diameter_mm"].as_f64().unwrap(),
                centre: (
                    case["centre"][0].as_f64().unwrap(),
                    case["centre"][1].as_f64().unwrap(),
                ),
                direction: ScoringDirection::from_name(case["direction"].as_str().unwrap()),
            };
            let got = score_shot(
                case["x"].as_f64().unwrap(),
                case["y"].as_f64().unwrap(),
                &ring_list(&case["rings"]),
                &options,
            );
            assert_eq!(got, case["label"].as_str().unwrap(), "{case}");
        }
    }

    #[test]
    fn label_to_value_matches_python() {
        let golden = load_golden("scoring");
        let cases = golden["label_to_value"].as_array().unwrap();
        assert!(!cases.is_empty());
        for case in cases {
            let label = case["label"].as_str().unwrap();
            let got = label_to_value(label);
            match &case["value"] {
                serde_json::Value::Null => assert_eq!(got, None, "{label:?}"),
                serde_json::Value::String(s) if s == "nan" => {
                    assert!(got.unwrap().is_nan(), "{label:?}")
                }
                serde_json::Value::String(s) if s == "inf" => {
                    assert_eq!(got, Some(f64::INFINITY), "{label:?}")
                }
                serde_json::Value::String(s) if s == "-inf" => {
                    assert_eq!(got, Some(f64::NEG_INFINITY), "{label:?}")
                }
                v => assert_close(got.unwrap(), v.as_f64().unwrap(), label),
            }
        }
    }

    #[test]
    fn total_score_matches_python() {
        let golden = load_golden("scoring");
        let cases = golden["total_score"].as_array().unwrap();
        assert!(!cases.is_empty());
        for case in cases {
            let labels: Vec<&str> = case["labels"]
                .as_array()
                .unwrap()
                .iter()
                .map(|l| l.as_str().unwrap())
                .collect();
            assert_close(
                total_score(labels),
                case["total"].as_f64().unwrap(),
                "total",
            );
        }
    }
}
