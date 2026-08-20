//! Coordinates camera capture, tracking, audio, storage and settings for a
//! front end, without depending on any interface framework.

pub mod backends;
pub mod controller;
pub mod convert;
pub mod devices;
pub mod events;
#[cfg(test)]
pub(crate) mod fakes;
pub mod frames;
pub mod paths;
pub mod player;
mod preview;
pub mod review;
pub mod runtime;
pub mod session;
pub mod watcher;

pub use backends::Backends;
pub use controller::{Command, Controller, ControllerConfig, ControllerError, ImageControl, Input};
pub use events::{UiEvent, UiSink};
pub use paths::DataPaths;
pub use runtime::{ControllerHandle, RuntimeOptions, monotonic_clock};
