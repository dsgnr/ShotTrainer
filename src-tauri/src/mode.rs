//! Chooses between the real devices and the synthetic ones.

use std::path::PathBuf;

use shottrainer_controller::{Backends, DataPaths};

use crate::fake;

pub const FAKE_DEVICES_FLAG: &str = "--fake-devices";
pub const FAKE_DEVICES_ENV: &str = "SHOTTRAINER_FAKE_DEVICES";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DeviceMode {
    System,
    Fake,
}

/// Fake devices when the flag is given, when the environment variable is
/// `1`, `true` or `yes` in any case, or when the build has no system
/// backends.
pub fn device_mode<I, S>(args: I, env_value: Option<&str>, system_available: bool) -> DeviceMode
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    let flag = args
        .into_iter()
        .any(|arg| arg.as_ref() == FAKE_DEVICES_FLAG);
    let env = env_value.is_some_and(|value| {
        ["1", "true", "yes"]
            .iter()
            .any(|on| value.trim().eq_ignore_ascii_case(on))
    });
    if flag || env || !system_available {
        DeviceMode::Fake
    } else {
        DeviceMode::System
    }
}

/// The OpenCV and `cpal` backends, or the synthetic ones.
pub fn backends(mode: DeviceMode) -> Backends {
    match mode {
        #[cfg(feature = "opencv")]
        DeviceMode::System => Backends::system(),
        _ => fake::backends(),
    }
}

/// Fake devices keep their sessions and settings in the temporary
/// directory, so synthetic shots never reach the user's data.
pub fn fake_data_dir() -> PathBuf {
    std::env::temp_dir().join("ShotTrainer-fake-devices")
}

pub fn data_paths(mode: DeviceMode) -> DataPaths {
    match mode {
        DeviceMode::System => DataPaths::system(),
        DeviceMode::Fake => {
            let dir = fake_data_dir();
            if let Err(error) = std::fs::create_dir_all(&dir) {
                log::warn!("Could not create {}: {error}", dir.display());
            }
            DataPaths::in_dir(&dir)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const NO_ARGS: [&str; 0] = [];

    #[test]
    fn system_devices_by_default_when_available() {
        assert_eq!(device_mode(NO_ARGS, None, true), DeviceMode::System);
    }

    #[test]
    fn the_flag_selects_fake_devices() {
        assert_eq!(
            device_mode(["--other", FAKE_DEVICES_FLAG], None, true),
            DeviceMode::Fake
        );
    }

    #[test]
    fn a_flag_that_only_starts_with_the_name_does_not() {
        assert_eq!(
            device_mode(["--fake-devices-later"], None, true),
            DeviceMode::System
        );
    }

    #[test]
    fn the_environment_selects_fake_devices_when_switched_on() {
        for on in ["1", "true", "YES", " True "] {
            assert_eq!(
                device_mode(NO_ARGS, Some(on), true),
                DeviceMode::Fake,
                "{on:?}"
            );
        }
        for off in ["", "0", "false", "no", "2"] {
            assert_eq!(
                device_mode(NO_ARGS, Some(off), true),
                DeviceMode::System,
                "{off:?}"
            );
        }
    }

    #[test]
    fn a_build_without_system_backends_always_uses_fake_devices() {
        assert_eq!(device_mode(NO_ARGS, None, false), DeviceMode::Fake);
    }

    #[test]
    fn fake_devices_keep_their_data_in_the_temporary_directory() {
        let dir = fake_data_dir();
        assert!(dir.starts_with(std::env::temp_dir()));
        assert_ne!(dir, std::env::temp_dir());
    }

    #[test]
    fn fake_backends_name_the_synthetic_camera() {
        let mut backends = backends(DeviceMode::Fake);
        assert_eq!(
            backends.camera.list_cameras(None),
            [(0, "Synthetic camera".to_owned())]
        );
    }
}
