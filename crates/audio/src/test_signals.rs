//! Integer signal recipes shared with the Python fixture generator.
//!
//! The generator state and every scale factor are integers or dyadic
//! fractions, so the samples are bit identical to the ones numpy produces in
//! `scripts/generate_golden.py`.

use serde_json::Value;

pub(crate) enum Segment {
    Noise { n: usize, amp: f32 },
    Dc { n: usize, level: f32 },
    Impulse { n: usize, amp: f32, decay: f32 },
    Silence { n: usize },
}

pub(crate) fn render(seed: u32, segments: &[Segment]) -> Vec<f32> {
    let mut state = seed;
    let mut out = Vec::new();
    for segment in segments {
        match *segment {
            Segment::Noise { n, amp } => {
                for _ in 0..n {
                    state = state.wrapping_mul(1664525).wrapping_add(1013904223);
                    let raw = ((state >> 8) & 0xFFFF) as f32;
                    out.push((raw / 32768.0 - 1.0) * amp);
                }
            }
            Segment::Dc { n, level } => out.resize(out.len() + n, level),
            Segment::Impulse { n, amp, decay } => {
                let mut value = amp;
                for _ in 0..n {
                    out.push(value);
                    value *= decay;
                }
            }
            Segment::Silence { n } => out.resize(out.len() + n, 0.0),
        }
    }
    out
}

fn number(segment: &Value, key: &str) -> f32 {
    segment[key]
        .as_f64()
        .unwrap_or_else(|| panic!("segment is missing {key}: {segment}")) as f32
}

fn parse_segment(segment: &Value) -> Segment {
    let n = segment["n"].as_u64().expect("segment length") as usize;
    match segment["kind"].as_str().expect("segment kind") {
        "noise" => Segment::Noise {
            n,
            amp: number(segment, "amp"),
        },
        "dc" => Segment::Dc {
            n,
            level: number(segment, "level"),
        },
        "impulse" => Segment::Impulse {
            n,
            amp: number(segment, "amp"),
            decay: number(segment, "decay"),
        },
        "silence" => Segment::Silence { n },
        other => panic!("unknown segment kind {other}"),
    }
}

/// Expands a fixture recipe of the form `{"seed": s, "segments": [...]}`.
pub(crate) fn render_recipe(recipe: &Value) -> Vec<f32> {
    let seed = recipe["seed"].as_u64().expect("recipe seed") as u32;
    let segments: Vec<Segment> = recipe["segments"]
        .as_array()
        .expect("recipe segments")
        .iter()
        .map(parse_segment)
        .collect();
    render(seed, &segments)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn noise_follows_the_integer_generator() {
        // state = 1 * 1664525 + 1013904223 = 1015568748, (state >> 8) & 0xFFFF = 0x8859.
        let samples = render(1, &[Segment::Noise { n: 1, amp: 1.0 }]);
        assert_eq!(samples, vec![0x8859 as f32 / 32768.0 - 1.0]);
    }

    #[test]
    fn impulse_decays_geometrically_and_segments_concatenate() {
        let samples = render(
            0,
            &[
                Segment::Silence { n: 2 },
                Segment::Impulse {
                    n: 3,
                    amp: 0.5,
                    decay: 0.5,
                },
                Segment::Dc { n: 1, level: 0.25 },
            ],
        );
        assert_eq!(samples, vec![0.0, 0.0, 0.5, 0.25, 0.125, 0.25]);
    }
}
