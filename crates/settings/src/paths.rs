use std::path::{Path, PathBuf};

const APP_NAME: &str = "ShotTrainer";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Platform {
    Windows,
    MacOs,
    Linux,
}

impl Platform {
    pub fn current() -> Self {
        if cfg!(target_os = "windows") {
            Self::Windows
        } else if cfg!(target_os = "macos") {
            Self::MacOs
        } else {
            Self::Linux
        }
    }
}

/// Resolves the data directory without touching the file system. An empty
/// `APPDATA` or `XDG_DATA_HOME` counts as unset.
pub fn data_dir_for(
    platform: Platform,
    env: &dyn Fn(&str) -> Option<String>,
    home: &Path,
) -> PathBuf {
    let non_empty = |name: &str| env(name).filter(|v| !v.is_empty());
    match platform {
        Platform::Windows => {
            let base = non_empty("APPDATA")
                .map(PathBuf::from)
                .unwrap_or_else(|| home.join("AppData").join("Roaming"));
            base.join(APP_NAME)
        }
        Platform::MacOs => home
            .join("Library")
            .join("Application Support")
            .join(APP_NAME),
        Platform::Linux => {
            let base = non_empty("XDG_DATA_HOME")
                .map(PathBuf::from)
                .unwrap_or_else(|| home.join(".local").join("share"));
            base.join("shottrainer")
        }
    }
}

/// The app's data directory, created if missing. A creation failure is
/// logged and the path is still returned, so callers report the real error
/// when they use it.
pub fn data_dir() -> PathBuf {
    let home = std::env::home_dir().unwrap_or_else(|| PathBuf::from("."));
    let path = data_dir_for(Platform::current(), &|k| std::env::var(k).ok(), &home);
    if let Err(err) = std::fs::create_dir_all(&path) {
        log::warn!("Could not create {}: {err}", path.display());
    }
    path
}

pub fn sessions_db_path() -> PathBuf {
    data_dir().join("sessions.db")
}

pub fn settings_path() -> PathBuf {
    data_dir().join("settings.json")
}
