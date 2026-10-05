//! The JSON the webview sends and receives. Field names are camelCase for
//! the TypeScript front end.

pub mod command;
pub mod event;
pub mod preferences;

pub use command::{WireCommand, WireImageControl};
pub use event::{UI_EVENT, WireEvent};
pub use preferences::WirePreferences;
