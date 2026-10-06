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
    /// Any string other than "outward" means inward.
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

/// Divides numeric scoring rings into equal tenths, capped at 10.9 on a
/// ten-ring target. An X ring supplies the ten only when no numeric ten exists.
/// Faces without numeric scores retain their labels.
pub fn score_shot_decimal(
    x_mm: f64,
    y_mm: f64,
    rings: &[ScoringRing],
    options: &ScoreOptions,
) -> String {
    let distance = (x_mm - options.centre.0).hypot(y_mm - options.centre.1);
    if !distance.is_finite() {
        return String::new();
    }
    let has_ten = rings
        .iter()
        .any(|ring| ring.label.parse::<f64>() == Ok(10.0));
    let mut numeric: Vec<(f64, f64)> = rings
        .iter()
        .filter_map(|ring| {
            let value = if !has_ten && ring.label.eq_ignore_ascii_case("X") {
                10.0
            } else {
                ring.label.parse::<f64>().ok()?
            };
            let radius = ring.radius_mm + options.shot_diameter_mm / 2.0;
            (value.is_finite() && value > 0.0 && radius.is_finite() && radius > 0.0)
                .then_some((radius, value))
        })
        .collect();
    numeric.sort_by(|a, b| a.0.total_cmp(&b.0));
    if numeric.is_empty()
        || numeric
            .windows(2)
            .any(|pair| pair[0].0 >= pair[1].0 || pair[0].1 <= pair[1].1)
    {
        return score_shot(x_mm, y_mm, rings, options);
    }
    let maximum = numeric[0].1 + 0.9;
    let mut inner_radius = 0.0;
    let mut inner_value = numeric[0].1 + 1.0;
    for (radius, value) in numeric {
        let inside = match options.direction {
            ScoringDirection::Inward => distance <= radius,
            ScoringDirection::Outward => distance < radius,
        };
        if inside {
            let scaled = 10.0
                * (value + (radius - distance) / (radius - inner_radius) * (inner_value - value));
            let nearest = scaled.round();
            // Remove arithmetic noise at a decimal boundary before applying its tie rule.
            let scaled = if (scaled - nearest).abs() <= 16.0 * f64::EPSILON * scaled.abs().max(1.0)
            {
                nearest
            } else {
                scaled
            };
            let scaled = if options.direction == ScoringDirection::Outward {
                scaled.next_down()
            } else {
                scaled
            };
            return format!("{:.1}", (scaled.floor() / 10.0).min(maximum));
        }
        inner_radius = radius;
        inner_value = value;
    }
    String::new()
}

/// Best-effort numeric value for a ring label. `X` scores 10 and anything
/// that does not parse as a finite number returns `None`.
pub fn label_to_value(label: &str) -> Option<f64> {
    if label.is_empty() {
        return None;
    }
    if label.to_uppercase() == "X" {
        return Some(10.0);
    }
    label
        .trim()
        .parse()
        .ok()
        .filter(|value: &f64| value.is_finite())
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
        .fold(0.0, |acc, v| acc + v)
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
    fn score_shot_matches_the_golden_cases() {
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

    fn decimal_rings() -> Vec<ScoringRing> {
        (1..=10)
            .rev()
            .map(|score| ScoringRing {
                radius_mm: 0.25 + f64::from(10 - score) * 2.5,
                label: score.to_string(),
            })
            .collect()
    }

    #[test]
    fn decimal_scoring_uses_equal_tenths_and_keeps_boundary_rules() {
        let rings = decimal_rings();
        let options = ScoreOptions {
            shot_diameter_mm: 4.5,
            ..ScoreOptions::default()
        };
        assert_eq!(score_shot_decimal(0.0, 0.0, &rings, &options), "10.9");
        for tenth in 10..=109 {
            let distance = (11.0 - (f64::from(tenth) / 10.0 + 0.05)) * 2.5;
            assert_eq!(
                score_shot_decimal(distance, 0.0, &rings, &options),
                format!("{:.1}", f64::from(tenth) / 10.0)
            );
        }
        assert_eq!(score_shot_decimal(2.5, 0.0, &rings, &options), "10.0");
        assert_eq!(score_shot_decimal(2.500_001, 0.0, &rings, &options), "9.9");
        assert_eq!(score_shot_decimal(25.0, 0.0, &rings, &options), "1.0");
        assert_eq!(score_shot_decimal(25.000_001, 0.0, &rings, &options), "");
        let outward = ScoreOptions {
            direction: ScoringDirection::Outward,
            ..options.clone()
        };
        assert_eq!(score_shot_decimal(2.5, 0.0, &rings, &outward), "9.9");
        assert_eq!(score_shot_decimal(25.0, 0.0, &rings, &outward), "");
        let shifted = ScoreOptions {
            centre: (3.0, 4.0),
            ..options
        };
        assert_eq!(score_shot_decimal(3.0, 4.0, &rings, &shifted), "10.9");
    }

    #[test]
    fn decimal_scoring_ignores_inner_x_when_a_ten_exists_and_rejects_nonfinite_positions() {
        let options = ScoreOptions {
            shot_diameter_mm: 4.5,
            ..ScoreOptions::default()
        };
        let mut rings = decimal_rings();
        rings.insert(
            0,
            ScoringRing {
                radius_mm: 0.1,
                label: "X".into(),
            },
        );
        assert_eq!(score_shot_decimal(2.4, 0.0, &rings, &options), "10.0");
        rings.retain(|r| r.label != "10");
        assert_eq!(score_shot_decimal(0.0, 0.0, &rings, &options), "10.9");
        for invalid in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            assert_eq!(score_shot_decimal(invalid, 0.0, &rings, &options), "");
        }
        assert_eq!(score_shot_decimal(0.0, 0.0, &[], &options), "");
        assert_eq!(
            score_shot_decimal(
                0.0,
                0.0,
                &[ScoringRing {
                    radius_mm: 3.0,
                    label: "A".into()
                }],
                &options
            ),
            "A"
        );
    }

    #[test]
    fn label_to_value_matches_the_golden_cases() {
        let golden = load_golden("scoring");
        let cases = golden["label_to_value"].as_array().unwrap();
        assert!(!cases.is_empty());
        for case in cases {
            let label = case["label"].as_str().unwrap();
            let got = label_to_value(label);
            match &case["value"] {
                serde_json::Value::Null => assert_eq!(got, None, "{label:?}"),
                v => assert_close(got.unwrap(), v.as_f64().unwrap(), label),
            }
        }
    }

    #[test]
    fn total_score_matches_the_golden_cases() {
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
            let got = total_score(labels);
            let expected = case["total"].as_f64().unwrap();
            assert_close(got, expected, "total");
            assert_eq!(got.to_bits(), expected.to_bits(), "sign of {case}");
        }
    }
}
