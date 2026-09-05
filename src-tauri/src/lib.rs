//! The Tauri shell. It hosts the webview, forwards commands to the
//! controller, emits controller events and delivers camera pixels.

pub mod fake;
mod logging;
pub mod mode;
pub mod pixels;
mod shell;
pub mod wire;

pub use shell::run;

#[cfg(test)]
mod tests {
    use serde_json::Value;

    const CONFIG: &str = include_str!("../tauri.conf.json");
    const INFO_PLIST: &str = include_str!("../Info.plist");

    #[test]
    fn the_bundle_keeps_the_python_identifier() {
        let config: Value = serde_json::from_str(CONFIG).unwrap();
        // macOS remembers camera and microphone consent per identifier.
        assert_eq!(config["identifier"], "org.shottrainer.app");
        assert_eq!(config["productName"], "ShotTrainer");
    }

    #[test]
    fn the_placeholder_page_can_reach_the_tauri_global() {
        let config: Value = serde_json::from_str(CONFIG).unwrap();
        assert_eq!(config["app"]["withGlobalTauri"], true);
        assert_eq!(config["app"]["windows"][0]["label"], "main");
    }

    #[test]
    fn the_bundle_explains_camera_and_microphone_use() {
        for line in [
            "<key>NSCameraUsageDescription</key>",
            "<string>ShotTrainer uses the camera to track the aiming point on the target.</string>",
            "<key>NSMicrophoneUsageDescription</key>",
            "<string>ShotTrainer listens for the sound of a shot to record hit timing.</string>",
        ] {
            assert!(INFO_PLIST.contains(line), "{line}");
        }
    }
}
