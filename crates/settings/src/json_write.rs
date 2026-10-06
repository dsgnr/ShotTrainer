//! Atomic JSON writing.

use std::io::Write;
use std::path::Path;

use serde::Serialize;

use crate::error::SettingsError;

/// Serialises `value` and replaces `path` through a temporary file in the same
/// directory, so a reader never sees a partial file. Creates missing parent
/// directories.
pub(crate) fn write_json_atomic<T: Serialize>(value: &T, path: &Path) -> Result<(), SettingsError> {
    let parent = match path.parent() {
        Some(p) if !p.as_os_str().is_empty() => p,
        _ => Path::new("."),
    };
    std::fs::create_dir_all(parent)?;
    let buf = serde_json::to_vec_pretty(value)?;
    let mut tmp = tempfile::NamedTempFile::new_in(parent)?;
    tmp.write_all(&buf)?;
    tmp.persist(path).map_err(|e| e.error)?;
    Ok(())
}
