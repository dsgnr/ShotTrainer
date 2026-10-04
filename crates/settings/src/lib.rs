//! User preferences and their persistence.

mod error;
mod json_values;
mod json_write;
mod paths;
mod preferences;
pub mod stores;

pub use error::SettingsError;
pub use paths::{Platform, data_dir, data_dir_for, sessions_db_path, settings_path};
pub use preferences::{Preferences, load_preferences, save_preferences};
