//! OpenCV-backed detector, optimiser scorer and camera source, built with the
//! `opencv` feature.

mod compat;
pub mod detector;
pub mod mat;

pub use detector::CircleTargetDetector;
