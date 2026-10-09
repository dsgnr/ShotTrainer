//! User preferences and their persistence.

mod error;
mod json_values;
mod json_write;
mod paths;
mod preferences;
pub mod stores;
pub mod target_faces;

pub use error::SettingsError;
pub use paths::{Platform, data_dir, data_dir_for};
pub use preferences::{Preferences, load_preferences, save_preferences, validate_preferences};
