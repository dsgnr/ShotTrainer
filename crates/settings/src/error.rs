/// Failure while saving settings. Loading never fails.
#[derive(Debug, thiserror::Error)]
pub enum SettingsError {
    #[error("settings file error: {0}")]
    Io(#[from] std::io::Error),
    #[error("settings encoding error: {0}")]
    Json(#[from] serde_json::Error),
}
