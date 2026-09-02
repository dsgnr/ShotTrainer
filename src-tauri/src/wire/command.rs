//! Commands as the webview sends them.

use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use shottrainer_controller::{Command, ImageControl};

use super::preferences::WirePreferences;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum WireImageControl {
    Brightness,
    Contrast,
}

impl From<WireImageControl> for ImageControl {
    fn from(control: WireImageControl) -> Self {
        match control {
            WireImageControl::Brightness => ImageControl::Brightness,
            WireImageControl::Contrast => ImageControl::Contrast,
        }
    }
}

/// A [`Command`] as the webview sends it, for example
/// `{"type": "deleteShot", "index": 2}`.
#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(
    tag = "type",
    rename_all = "camelCase",
    rename_all_fields = "camelCase",
    deny_unknown_fields
)]
pub enum WireCommand {
    StartSession {
        name: String,
        category: String,
    },
    StopSession,
    ClearShots,
    DeleteShot {
        index: usize,
    },
    Rescore,
    SelectShot {
        index: usize,
    },
    ListSessions,
    OpenSession {
        id: i64,
    },
    RenameSession {
        id: i64,
        name: String,
    },
    SetSessionCategory {
        id: i64,
        category: String,
    },
    DeleteSession {
        id: i64,
    },
    ExportSession {
        id: i64,
        dir: PathBuf,
    },
    ReplayPlay,
    ReplayPause,
    ReplayReset,
    ReplaySeek {
        fraction: f64,
    },
    SetPreferences {
        prefs: WirePreferences,
    },
    SetCircleDiameter {
        diameter_mm: f64,
    },
    ZeroOnAim,
    ClearZero,
    Refresh,
    ListDevices {
        refresh: bool,
    },
    ListTargetFaces,
    BeginPreview {
        camera_id: Option<i32>,
    },
    PreviewCamera {
        camera_id: Option<i32>,
    },
    PreviewImage {
        control: WireImageControl,
        value: f64,
    },
    PreviewTransform {
        rotation_degrees: i32,
        flip_horizontal: bool,
        flip_vertical: bool,
    },
    EndPreview {
        saved: bool,
    },
    Optimise,
    ResetDetector,
}

impl From<WireCommand> for Command {
    fn from(command: WireCommand) -> Self {
        match command {
            WireCommand::StartSession { name, category } => {
                Command::StartSession { name, category }
            }
            WireCommand::StopSession => Command::StopSession,
            WireCommand::ClearShots => Command::ClearShots,
            WireCommand::DeleteShot { index } => Command::DeleteShot(index),
            WireCommand::Rescore => Command::Rescore,
            WireCommand::SelectShot { index } => Command::SelectShot(index),
            WireCommand::ListSessions => Command::ListSessions,
            WireCommand::OpenSession { id } => Command::OpenSession(id),
            WireCommand::RenameSession { id, name } => Command::RenameSession { id, name },
            WireCommand::SetSessionCategory { id, category } => {
                Command::SetSessionCategory { id, category }
            }
            WireCommand::DeleteSession { id } => Command::DeleteSession(id),
            WireCommand::ExportSession { id, dir } => Command::ExportSession { id, dir },
            WireCommand::ReplayPlay => Command::ReplayPlay,
            WireCommand::ReplayPause => Command::ReplayPause,
            WireCommand::ReplayReset => Command::ReplayReset,
            WireCommand::ReplaySeek { fraction } => Command::ReplaySeek(fraction),
            WireCommand::SetPreferences { prefs } => Command::SetPreferences(prefs.into()),
            WireCommand::SetCircleDiameter { diameter_mm } => {
                Command::SetCircleDiameter(diameter_mm)
            }
            WireCommand::ZeroOnAim => Command::ZeroOnAim,
            WireCommand::ClearZero => Command::ClearZero,
            WireCommand::Refresh => Command::Refresh,
            WireCommand::ListDevices { refresh } => Command::ListDevices { refresh },
            WireCommand::ListTargetFaces => Command::ListTargetFaces,
            WireCommand::BeginPreview { camera_id } => Command::BeginPreview { camera_id },
            WireCommand::PreviewCamera { camera_id } => Command::PreviewCamera(camera_id),
            WireCommand::PreviewImage { control, value } => Command::PreviewImage {
                control: control.into(),
                value,
            },
            WireCommand::PreviewTransform {
                rotation_degrees,
                flip_horizontal,
                flip_vertical,
            } => Command::PreviewTransform {
                rotation_degrees,
                flip_horizontal,
                flip_vertical,
            },
            WireCommand::EndPreview { saved } => Command::EndPreview { saved },
            WireCommand::Optimise => Command::Optimise,
            WireCommand::ResetDetector => Command::ResetDetector,
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::{Value, json};

    use super::*;
    use crate::wire::preferences::tests::distinct_preferences;

    fn command(text: Value) -> Command {
        serde_json::from_value::<WireCommand>(text).unwrap().into()
    }

    #[test]
    fn every_command_maps_to_its_controller_command() {
        let prefs = distinct_preferences();
        let cases = [
            (
                json!({"type": "startSession", "name": "Morning", "category": "match"}),
                Command::StartSession {
                    name: "Morning".into(),
                    category: "match".into(),
                },
            ),
            (json!({"type": "stopSession"}), Command::StopSession),
            (json!({"type": "clearShots"}), Command::ClearShots),
            (
                json!({"type": "deleteShot", "index": 2}),
                Command::DeleteShot(2),
            ),
            (json!({"type": "rescore"}), Command::Rescore),
            (
                json!({"type": "selectShot", "index": 4}),
                Command::SelectShot(4),
            ),
            (json!({"type": "listSessions"}), Command::ListSessions),
            (
                json!({"type": "openSession", "id": 7}),
                Command::OpenSession(7),
            ),
            (
                json!({"type": "renameSession", "id": 7, "name": "Evening"}),
                Command::RenameSession {
                    id: 7,
                    name: "Evening".into(),
                },
            ),
            (
                json!({"type": "setSessionCategory", "id": 8, "category": "sighter"}),
                Command::SetSessionCategory {
                    id: 8,
                    category: "sighter".into(),
                },
            ),
            (
                json!({"type": "deleteSession", "id": 9}),
                Command::DeleteSession(9),
            ),
            (
                json!({"type": "exportSession", "id": 10, "dir": "exports"}),
                Command::ExportSession {
                    id: 10,
                    dir: PathBuf::from("exports"),
                },
            ),
            (json!({"type": "replayPlay"}), Command::ReplayPlay),
            (json!({"type": "replayPause"}), Command::ReplayPause),
            (json!({"type": "replayReset"}), Command::ReplayReset),
            (
                json!({"type": "replaySeek", "fraction": 0.25}),
                Command::ReplaySeek(0.25),
            ),
            (
                json!({"type": "setPreferences", "prefs": WirePreferences::from(&prefs)}),
                Command::SetPreferences(prefs.clone()),
            ),
            (
                json!({"type": "setCircleDiameter", "diameterMm": 42.5}),
                Command::SetCircleDiameter(42.5),
            ),
            (json!({"type": "zeroOnAim"}), Command::ZeroOnAim),
            (json!({"type": "clearZero"}), Command::ClearZero),
            (json!({"type": "refresh"}), Command::Refresh),
            (
                json!({"type": "listDevices", "refresh": true}),
                Command::ListDevices { refresh: true },
            ),
            (json!({"type": "listTargetFaces"}), Command::ListTargetFaces),
            (
                json!({"type": "beginPreview", "cameraId": 1}),
                Command::BeginPreview { camera_id: Some(1) },
            ),
            (
                json!({"type": "previewCamera", "cameraId": null}),
                Command::PreviewCamera(None),
            ),
            (
                json!({"type": "previewImage", "control": "brightness", "value": 10.0}),
                Command::PreviewImage {
                    control: ImageControl::Brightness,
                    value: 10.0,
                },
            ),
            (
                json!({"type": "previewImage", "control": "contrast", "value": 1.5}),
                Command::PreviewImage {
                    control: ImageControl::Contrast,
                    value: 1.5,
                },
            ),
            (
                json!({"type": "previewTransform", "rotationDegrees": 90, "flipHorizontal": true, "flipVertical": false}),
                Command::PreviewTransform {
                    rotation_degrees: 90,
                    flip_horizontal: true,
                    flip_vertical: false,
                },
            ),
            (
                json!({"type": "endPreview", "saved": true}),
                Command::EndPreview { saved: true },
            ),
            (json!({"type": "optimise"}), Command::Optimise),
            (json!({"type": "resetDetector"}), Command::ResetDetector),
        ];
        for (text, expected) in cases {
            assert_eq!(command(text.clone()), expected, "{text}");
        }
    }

    #[test]
    fn malformed_commands_are_refused() {
        for text in [
            json!({"type": "deleteShot", "index": -1}),
            json!({"type": "deleteShot"}),
            json!({"type": "launchMissiles"}),
            json!({"type": "replaySeek", "fraction": null}),
            json!({"type": "beginPreview", "camera_id": 1}),
            json!({"type": "previewImage", "control": "gamma", "value": 1.0}),
            json!({"index": 1}),
        ] {
            assert!(
                serde_json::from_value::<WireCommand>(text.clone()).is_err(),
                "{text}"
            );
        }
    }
}
