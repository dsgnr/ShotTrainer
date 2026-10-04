//! Audio capture and shot detection.

pub mod models;
pub mod shot_detector;

#[cfg(test)]
pub(crate) mod test_signals;

pub use shot_detector::ShotDetector;
