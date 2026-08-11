//! Camera capture, target detection, frame transforms and the live tracker.

pub mod capture;
#[cfg(feature = "opencv")]
pub mod cv;
pub mod detector;
pub mod frame;
pub mod frame_ops;
pub mod log_limit;
pub mod models;
pub mod tracker;
pub mod tuning;

#[cfg(test)]
pub(crate) mod test_support;
