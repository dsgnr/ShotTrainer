//! Port of `app/settings_watcher.py`. Python polls the modification time of
//! `settings.json` on a timer. The controller runtime calls
//! [`SettingsWatcher::poll`] every [`POLL_INTERVAL`].

use std::path::PathBuf;
use std::time::{Duration, SystemTime};

use shottrainer_settings::{Preferences, load_preferences};

pub const POLL_INTERVAL: Duration = Duration::from_millis(1500);

#[derive(Debug, Clone)]
pub struct SettingsWatcher {
    path: PathBuf,
    mtime: Option<SystemTime>,
}

impl SettingsWatcher {
    pub fn new(path: PathBuf) -> Self {
        SettingsWatcher { path, mtime: None }
    }

    /// Takes the current modification time as the baseline, so a file that
    /// already exists is not reported as a change.
    pub fn start(&mut self) {
        self.mark_seen();
    }

    /// Resets the baseline after the controller writes the file itself, so
    /// only edits from elsewhere are reported.
    pub fn mark_seen(&mut self) {
        self.mtime = self.current_mtime();
    }

    /// Returns the preferences when the modification time differs from the
    /// baseline. A file that has gone gives the defaults, so stale values are
    /// not kept.
    pub fn poll(&mut self) -> Option<Preferences> {
        let current = self.current_mtime();
        if current == self.mtime {
            return None;
        }
        self.mtime = current;
        Some(match current {
            None => Preferences::default(),
            Some(_) => load_preferences(&self.path),
        })
    }

    /// `None` when the file is missing or cannot be inspected.
    fn current_mtime(&self) -> Option<SystemTime> {
        match std::fs::metadata(&self.path).and_then(|m| m.modified()) {
            Ok(mtime) => Some(mtime),
            Err(error) => {
                if error.kind() != std::io::ErrorKind::NotFound {
                    log::debug!("Could not stat {}: {error}", self.path.display());
                }
                None
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use std::fs::File;
    use std::path::Path;

    use shottrainer_settings::save_preferences;

    use super::*;

    /// Gives the file a modification time `seconds` after the epoch, so tests
    /// do not depend on the file system's timestamp resolution.
    fn set_mtime(path: &Path, seconds: u64) {
        let file = File::options().write(true).open(path).unwrap();
        file.set_modified(SystemTime::UNIX_EPOCH + Duration::from_secs(seconds))
            .unwrap();
    }

    fn save(path: &Path, prefs: &Preferences, seconds: u64) {
        save_preferences(prefs, path).unwrap();
        set_mtime(path, seconds);
    }

    fn with_camera(id: i32) -> Preferences {
        Preferences {
            camera_id: Some(id),
            ..Preferences::default()
        }
    }

    #[test]
    fn no_change_when_file_missing() {
        let dir = tempfile::tempdir().unwrap();
        let mut watcher = SettingsWatcher::new(dir.path().join("absent.json"));
        watcher.start();
        assert_eq!(watcher.poll(), None);
    }

    #[test]
    fn emits_when_file_appears() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        let mut watcher = SettingsWatcher::new(path.clone());
        watcher.start();
        save(&path, &with_camera(2), 1_000);
        assert_eq!(watcher.poll().and_then(|p| p.camera_id), Some(2));
        assert_eq!(watcher.poll(), None, "one change is reported once");
    }

    #[test]
    fn an_existing_file_is_not_a_change() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        save(&path, &with_camera(1), 1_000);
        let mut watcher = SettingsWatcher::new(path);
        watcher.start();
        assert_eq!(watcher.poll(), None);
    }

    #[test]
    fn no_emit_after_mark_seen() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        save(&path, &Preferences::default(), 1_000);
        let mut watcher = SettingsWatcher::new(path.clone());
        watcher.start();
        save(&path, &with_camera(4), 2_000);
        watcher.mark_seen();
        assert_eq!(watcher.poll(), None);
    }

    #[test]
    fn a_later_edit_is_reported() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        save(&path, &with_camera(1), 1_000);
        let mut watcher = SettingsWatcher::new(path.clone());
        watcher.start();
        save(&path, &with_camera(5), 2_000);
        assert_eq!(watcher.poll(), Some(with_camera(5)));
    }

    #[test]
    fn emits_defaults_when_file_removed() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        save(&path, &with_camera(3), 1_000);
        let mut watcher = SettingsWatcher::new(path.clone());
        watcher.start();
        std::fs::remove_file(&path).unwrap();
        assert_eq!(watcher.poll(), Some(Preferences::default()));
        assert_eq!(watcher.poll(), None);
    }

    #[test]
    fn a_malformed_edit_gives_defaults() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        save(&path, &with_camera(3), 1_000);
        let mut watcher = SettingsWatcher::new(path.clone());
        watcher.start();
        std::fs::write(&path, "{ not json").unwrap();
        set_mtime(&path, 2_000);
        assert_eq!(watcher.poll(), Some(Preferences::default()));
    }
}
