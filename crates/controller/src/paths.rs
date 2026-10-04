//! Every file the controller reads or writes, resolved from one directory so
//! tests never touch the real data directory.

use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DataPaths {
    pub sessions_db: PathBuf,
    pub settings: PathBuf,
    pub detector_settings: PathBuf,
    pub zero_offset: PathBuf,
    pub camera_selection: PathBuf,
    pub custom_target_faces: PathBuf,
}

impl DataPaths {
    /// The file names the Python application uses inside `dir`.
    pub fn in_dir(dir: &Path) -> Self {
        DataPaths {
            sessions_db: dir.join("sessions.db"),
            settings: dir.join("settings.json"),
            detector_settings: dir.join("detector_settings.json"),
            zero_offset: dir.join("zero_offset.json"),
            camera_selection: dir.join("camera_selection.json"),
            custom_target_faces: dir.join("custom_target_faces.json"),
        }
    }

    /// The platform data directory, created if missing.
    pub fn system() -> Self {
        Self::in_dir(&shottrainer_settings::data_dir())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn file_names_match_python() {
        let paths = DataPaths::in_dir(Path::new("data"));
        let names: Vec<_> = [
            &paths.sessions_db,
            &paths.settings,
            &paths.detector_settings,
            &paths.zero_offset,
            &paths.camera_selection,
            &paths.custom_target_faces,
        ]
        .iter()
        .map(|p| p.strip_prefix("data").unwrap().to_str().unwrap().to_owned())
        .collect();
        assert_eq!(
            names,
            [
                "sessions.db",
                "settings.json",
                "detector_settings.json",
                "zero_offset.json",
                "camera_selection.json",
                "custom_target_faces.json",
            ]
        );
    }
}
