#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ShotEvent {
    pub timestamp: f64,
    pub audio_level: f64,
    pub sample_rate: u32,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ShotDetectorSettings {
    pub threshold: f64,
    pub refractory_ms: u32,
    pub block_size: usize,
    pub sample_rate: u32,
    pub high_pass_alpha: f64,
}

impl Default for ShotDetectorSettings {
    fn default() -> Self {
        ShotDetectorSettings {
            threshold: 0.25,
            refractory_ms: 400,
            block_size: 1024,
            sample_rate: 44100,
            high_pass_alpha: 0.97,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shot_detector_defaults_match_python() {
        let s = ShotDetectorSettings::default();
        assert_eq!(
            (
                s.threshold,
                s.refractory_ms,
                s.block_size,
                s.sample_rate,
                s.high_pass_alpha
            ),
            (0.25, 400, 1024, 44100, 0.97)
        );
    }
}
