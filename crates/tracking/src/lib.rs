//! Camera capture, target detection, frame transforms and the live tracker.

pub mod detector;
pub mod frame;
pub mod frame_ops;
pub mod models;
pub mod tracker;

#[cfg(test)]
pub(crate) mod test_support;
