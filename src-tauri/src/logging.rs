//! Writes `log` records at info level and above to standard error and to
//! `app.log` in the data directory.

use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::sync::Mutex;

use log::{Level, LevelFilter, Log, Metadata, Record};

const LOG_FILE: &str = "app.log";

/// The file is truncated at start-up once it passes this size.
const MAX_LOG_BYTES: u64 = 1024 * 1024;

struct AppLogger {
    file: Mutex<Option<File>>,
}

impl Log for AppLogger {
    fn enabled(&self, metadata: &Metadata) -> bool {
        metadata.level() <= Level::Info
    }

    fn log(&self, record: &Record) {
        if !self.enabled(record.metadata()) {
            return;
        }
        let line = format!("{} {}: {}", record.level(), record.target(), record.args());
        eprintln!("{line}");
        if let Ok(mut file) = self.file.lock()
            && let Some(file) = file.as_mut()
        {
            let _ = writeln!(file, "{line}");
        }
    }

    fn flush(&self) {}
}

static LOGGER: AppLogger = AppLogger {
    file: Mutex::new(None),
};

fn open_log(dir: &Path, max_bytes: u64) -> Option<File> {
    std::fs::create_dir_all(dir).ok()?;
    let path = dir.join(LOG_FILE);
    if std::fs::metadata(&path).is_ok_and(|m| m.len() > max_bytes) {
        File::create(&path).ok()?;
    }
    OpenOptions::new().create(true).append(true).open(path).ok()
}

/// Installs the logger unless another one is already set. A log file that
/// cannot be opened leaves logging on standard error only.
pub fn init(data_dir: &Path) {
    if log::set_logger(&LOGGER).is_ok() {
        if let Ok(mut file) = LOGGER.file.lock() {
            *file = open_log(data_dir, MAX_LOG_BYTES);
        }
        log::set_max_level(LevelFilter::Info);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_log_over_the_limit_is_truncated_and_a_small_one_appended_to() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(LOG_FILE);
        std::fs::write(&path, "0123456789").unwrap();

        writeln!(open_log(dir.path(), 10).unwrap(), "a").unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "0123456789a\n");

        writeln!(open_log(dir.path(), 5).unwrap(), "b").unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "b\n");
    }
}
