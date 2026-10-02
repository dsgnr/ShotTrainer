//! The Tauri shell. It hosts the webview, forwards commands to the
//! controller, emits controller events and delivers camera pixels.

pub mod bridge;
pub mod fake;
mod logging;
pub mod mode;
pub mod permissions;
pub mod pixels;
mod shell;
pub mod wire;

pub use shell::run;

#[cfg(test)]
mod tests {
    use serde_json::Value;

    const CAPABILITIES: &str = include_str!("../capabilities/default.json");
    const CONFIG: &str = include_str!("../tauri.conf.json");
    const INFO_PLIST: &str = include_str!("../Info.plist");
    const VITE_CONFIG: &str = include_str!("../../frontend/vite.config.ts");

    #[test]
    fn the_main_window_only_receives_required_event_permissions() {
        let capability: Value = serde_json::from_str(CAPABILITIES).unwrap();
        assert_eq!(capability["windows"], serde_json::json!(["main"]));
        assert_eq!(
            capability["permissions"],
            serde_json::json!([
                "core:event:allow-listen",
                "core:event:allow-unlisten",
                "core:app:allow-version",
                "core:webview:allow-print",
                "core:resources:allow-close",
                "updater:allow-check",
                "updater:allow-download",
                "updater:allow-install",
                "process:allow-restart",
                {"identifier": "opener:allow-open-url", "allow": [
                    {"url": "https://github.com/dsgnr/ShotTrainer"},
                    {"url": "https://github.com/dsgnr/ShotTrainer/releases"}
                ]}
            ])
        );
    }

    #[test]
    fn the_bundle_keeps_the_python_identifier() {
        let config: Value = serde_json::from_str(CONFIG).unwrap();
        // macOS remembers camera and microphone consent per identifier.
        assert_eq!(config["identifier"], "org.shottrainer.app");
        assert_eq!(config["productName"], "ShotTrainer");
    }

    #[test]
    fn macos_uses_the_product_name_in_system_ui() {
        let config: Value = serde_json::from_str(CONFIG).unwrap();
        let name = config["productName"].as_str().unwrap();
        let manifest = include_str!("../Cargo.toml");
        assert!(manifest.contains(&format!("default-run = \"{name}\"")));
        assert!(manifest.contains(&format!("[[bin]]\nname = \"{name}\"")));
        for key in ["CFBundleName", "CFBundleDisplayName"] {
            assert!(INFO_PLIST.contains(&format!("<key>{key}</key>\n  <string>{name}</string>")));
        }
    }

    #[test]
    fn the_window_loads_the_vite_front_end() {
        let config: Value = serde_json::from_str(CONFIG).unwrap();
        let build = &config["build"];
        assert_eq!(build["devUrl"], "http://localhost:5173");
        assert_eq!(build["frontendDist"], "../frontend/dist");
        assert_eq!(build["beforeDevCommand"]["script"], "npm run dev");
        assert_eq!(build["beforeDevCommand"]["cwd"], "../frontend");
        assert_eq!(build["beforeBuildCommand"]["script"], "npm run build");
        assert_eq!(build["beforeBuildCommand"]["cwd"], "../frontend");
        assert!(VITE_CONFIG.contains("port: 5173,"));
        assert!(VITE_CONFIG.contains("strictPort: true,"));
        assert!(VITE_CONFIG.contains(r#"outDir: "dist","#));
        // The page imports `@tauri-apps/api`, so no script needs the global.
        assert_eq!(config["app"].get("withGlobalTauri"), None);
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
