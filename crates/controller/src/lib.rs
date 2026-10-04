//! Coordinates camera capture, tracking, audio, storage and settings for a
//! front end, without depending on any interface framework.

pub mod convert;
pub mod events;
pub mod paths;
pub mod player;
pub mod session;
pub mod watcher;

pub use paths::DataPaths;
