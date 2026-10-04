#[derive(Debug, Clone, PartialEq)]
pub struct TrackingSample {
    pub timestamp: f64,
    pub x_px: f64,
    pub y_px: f64,
    pub x_mm: Option<f64>,
    pub y_mm: Option<f64>,
    pub confidence: f64,
    pub frame_id: i64,
}

impl TrackingSample {
    pub fn new(timestamp: f64, x_px: f64, y_px: f64) -> Self {
        TrackingSample {
            timestamp,
            x_px,
            y_px,
            x_mm: None,
            y_mm: None,
            confidence: 1.0,
            frame_id: 0,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct Detection {
    pub found: bool,
    pub x_px: f64,
    pub y_px: f64,
    pub radius_px: f64,
    pub confidence: f64,
    pub rejected_outside_region: bool,
    pub semi_major_px: f64,
    pub semi_minor_px: f64,
    pub angle_degrees: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CameraFrame {
    pub frame_id: i64,
    pub timestamp: f64,
    pub width: u32,
    pub height: u32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tracking_sample_defaults_match_python() {
        let s = TrackingSample::new(1.5, 10.0, 20.0);
        assert_eq!(
            (s.confidence, s.frame_id, s.x_mm, s.y_mm),
            (1.0, 0, None, None)
        );
    }

    #[test]
    fn detection_default_has_found_false() {
        let d = Detection::default();
        assert!(!d.found);
    }

    #[test]
    fn detection_default_has_zeros() {
        let d = Detection::default();
        assert_eq!(d.x_px, 0.0);
        assert_eq!(d.y_px, 0.0);
        assert_eq!(d.radius_px, 0.0);
        assert_eq!(d.confidence, 0.0);
        assert!(!d.rejected_outside_region);
        assert_eq!(d.semi_major_px, 0.0);
        assert_eq!(d.semi_minor_px, 0.0);
        assert_eq!(d.angle_degrees, 0.0);
    }
}
