//! Coordinates camera capture, tracking, audio, storage and settings for a
//! front end, without depending on any interface framework.

pub mod backends;
pub mod convert;
pub mod devices;
pub mod events;
#[cfg(test)]
pub(crate) mod fakes;
pub mod frames;
pub mod paths;
pub mod player;
pub mod review;
pub mod session;
pub mod watcher;

pub use backends::Backends;
pub use paths::DataPaths;
