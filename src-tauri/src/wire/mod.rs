//! The JSON the webview sends and receives. Field names are camelCase for
//! the TypeScript front end.

pub mod command;
pub mod preferences;

pub use command::{WireCommand, WireImageControl};
pub use preferences::WirePreferences;
