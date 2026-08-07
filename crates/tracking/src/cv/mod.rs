//! OpenCV-backed detector, optimiser scorer and camera source, built with the
//! `opencv` feature.

mod compat;
pub mod detector;
pub mod mat;
pub mod tuning;

pub use detector::CircleTargetDetector;
pub use tuning::OpenCvHoughScorer;
