//! Controller events as the webview receives them. Numbers that are not
//! finite are written as `null`.

use serde::Serialize;
use shottrainer_controller::UiEvent;
use shottrainer_controller::events::{
    HoldTrace, HoldZone, ReplayView, Severity, ShotsView, StatusMessage,
};
use shottrainer_controller::frames::{FrameView, Marker, TrackingStatus};
use shottrainer_controller::player::PlayerEvent;
use shottrainer_controller::session::{SessionState, ShotEntry};
use shottrainer_core::services::shot_stats::{ShotStats, TraceStats};
use shottrainer_core::sessions::SessionSummary;
use shottrainer_settings::target_faces::{TargetFace, TargetRing};

use super::preferences::WirePreferences;

/// The Tauri event every [`WireEvent`] is emitted under.
pub const UI_EVENT: &str = "ui-event";

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireMessage {
    pub text: String,
    pub severity: &'static str,
    pub duration_ms: u32,
}

impl From<&StatusMessage> for WireMessage {
    fn from(m: &StatusMessage) -> Self {
        WireMessage {
            text: m.text.clone(),
            severity: match m.severity {
                Severity::Info => "info",
                Severity::Warning => "warning",
                Severity::Success => "success",
            },
            duration_ms: m.duration_ms,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireMarker {
    pub x_px: f64,
    pub y_px: f64,
    pub radius_px: f64,
}

impl From<&Marker> for WireMarker {
    fn from(m: &Marker) -> Self {
        WireMarker {
            x_px: m.x_px,
            y_px: m.y_px,
            radius_px: m.radius_px,
        }
    }
}

/// Everything about a frame except its pixels, which travel separately on
/// the frame channel. Sent as an event so the trace point keeps its order
/// relative to `clearLiveTrace` and the other events.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireFrame {
    pub frame_id: i64,
    pub timestamp: f64,
    pub width: u32,
    pub height: u32,
    pub status: &'static str,
    pub aim: Option<WireMarker>,
    pub rejected: Option<WireMarker>,
    pub zero_px: Option<(f64, f64)>,
    pub trace_point_mm: Option<(f64, f64)>,
}

impl From<&FrameView> for WireFrame {
    fn from(v: &FrameView) -> Self {
        WireFrame {
            frame_id: v.frame_id,
            timestamp: v.timestamp,
            width: v.frame.width(),
            height: v.frame.height(),
            status: match v.status {
                TrackingStatus::Idle => "idle",
                TrackingStatus::Tracking => "tracking",
                TrackingStatus::Lost => "lost",
                TrackingStatus::Rejected => "rejected",
            },
            aim: v.aim.as_ref().map(WireMarker::from),
            rejected: v.rejected.as_ref().map(WireMarker::from),
            zero_px: v.zero_px,
            trace_point_mm: v.trace_point_mm,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireRing {
    pub diameter_mm: f64,
    pub label: Option<String>,
}

impl From<&TargetRing> for WireRing {
    fn from(r: &TargetRing) -> Self {
        WireRing {
            diameter_mm: r.diameter_mm,
            label: r.label.clone(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireFace {
    pub key: String,
    pub label: String,
    pub rings: Vec<WireRing>,
    pub shot_diameter_mm: Option<f64>,
    pub face_diameter_mm: Option<f64>,
    pub scoring_direction: String,
}

impl From<&TargetFace> for WireFace {
    fn from(f: &TargetFace) -> Self {
        WireFace {
            key: f.key.clone(),
            label: f.label.clone(),
            rings: f.rings.iter().map(WireRing::from).collect(),
            shot_diameter_mm: f.shot_diameter_mm,
            face_diameter_mm: f.face_diameter_mm,
            scoring_direction: f.scoring_direction.clone(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireCamera {
    pub index: i64,
    pub name: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(
    tag = "kind",
    rename_all = "camelCase",
    rename_all_fields = "camelCase"
)]
pub enum WireSessionState {
    Idle,
    Recording { session_id: i64 },
    Reviewing { session_id: i64 },
}

impl From<SessionState> for WireSessionState {
    fn from(state: SessionState) -> Self {
        match state {
            SessionState::Idle => WireSessionState::Idle,
            SessionState::Recording(session_id) => WireSessionState::Recording { session_id },
            SessionState::Reviewing(session_id) => WireSessionState::Reviewing { session_id },
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireShot {
    pub timestamp: f64,
    pub x_mm: Option<f64>,
    pub y_mm: Option<f64>,
    pub score: Option<String>,
    pub shot_id: Option<i64>,
}

impl From<&ShotEntry> for WireShot {
    fn from(s: &ShotEntry) -> Self {
        WireShot {
            timestamp: s.timestamp,
            x_mm: s.x_mm,
            y_mm: s.y_mm,
            score: s.score.clone(),
            shot_id: s.shot_id,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireShotStats {
    pub count: usize,
    pub mean_x_mm: f64,
    pub mean_y_mm: f64,
    pub extreme_spread_mm: f64,
    pub mean_radius_mm: f64,
}

impl From<&ShotStats> for WireShotStats {
    fn from(s: &ShotStats) -> Self {
        WireShotStats {
            count: s.count,
            mean_x_mm: s.mean_x_mm,
            mean_y_mm: s.mean_y_mm,
            extreme_spread_mm: s.extreme_spread_mm,
            mean_radius_mm: s.mean_radius_mm,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireTraceStats {
    pub samples: usize,
    pub hold_tremor_mm: f64,
    pub trace_length_mm: f64,
    pub mean_x_mm: f64,
    pub mean_y_mm: f64,
}

impl From<&TraceStats> for WireTraceStats {
    fn from(s: &TraceStats) -> Self {
        WireTraceStats {
            samples: s.samples,
            hold_tremor_mm: s.hold_tremor_mm,
            trace_length_mm: s.trace_length_mm,
            mean_x_mm: s.mean_x_mm,
            mean_y_mm: s.mean_y_mm,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireHoldTrace {
    pub points: Vec<(f64, f64)>,
    pub stats: WireTraceStats,
}

impl From<&HoldTrace> for WireHoldTrace {
    fn from(h: &HoldTrace) -> Self {
        WireHoldTrace {
            points: h.points.clone(),
            stats: (&h.stats).into(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireHoldZone {
    pub centre_mm: (f64, f64),
    pub radius_mm: f64,
}

impl From<&HoldZone> for WireHoldZone {
    fn from(z: &HoldZone) -> Self {
        WireHoldZone {
            centre_mm: z.centre_mm,
            radius_mm: z.radius_mm,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireReplay {
    pub index: usize,
    pub points: Vec<(f64, f64)>,
    pub release_index: Option<usize>,
    pub split_index: Option<usize>,
    pub duration_ms: Option<i64>,
    pub hold_zone: Option<WireHoldZone>,
    pub enabled: bool,
}

impl From<&ReplayView> for WireReplay {
    fn from(r: &ReplayView) -> Self {
        WireReplay {
            index: r.index,
            points: r.points.clone(),
            release_index: r.release_index,
            split_index: r.split_index,
            duration_ms: r.duration_ms,
            hold_zone: r.hold_zone.as_ref().map(WireHoldZone::from),
            enabled: r.enabled,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WireSessionSummary {
    pub id: i64,
    pub name: String,
    /// ISO 8601 local time without a zone, as stored in `sessions.db`.
    pub started_at: String,
    pub ended_at: Option<String>,
    pub shot_count: i64,
    pub total_score: f64,
    pub category: String,
}

const STORED_TIME: &str = "%Y-%m-%dT%H:%M:%S%.f";

impl From<&SessionSummary> for WireSessionSummary {
    fn from(s: &SessionSummary) -> Self {
        WireSessionSummary {
            id: s.id,
            name: s.name.clone(),
            started_at: s.started_at.format(STORED_TIME).to_string(),
            ended_at: s.ended_at.map(|t| t.format(STORED_TIME).to_string()),
            shot_count: s.shot_count,
            total_score: s.total_score,
            category: s.category.clone(),
        }
    }
}

/// A [`UiEvent`] as the webview receives it, for example
/// `{"type": "audioLevel", "level": 0.12}`.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(
    tag = "type",
    rename_all = "camelCase",
    rename_all_fields = "camelCase"
)]
pub enum WireEvent {
    Frame(WireFrame),
    CameraIdle,
    AudioLevel {
        level: f64,
    },
    TrackingStatusText {
        text: String,
    },
    Preferences {
        prefs: WirePreferences,
        rings: Vec<WireRing>,
    },
    ZeroOffset {
        active: bool,
        offset_mm: (f64, f64),
    },
    ClearLiveTrace,
    DeviceOptions {
        cameras: Vec<WireCamera>,
        microphones: Vec<String>,
        saved_camera: String,
    },
    TargetFaces {
        faces: Vec<WireFace>,
    },
    DetectorStatus {
        message: WireMessage,
    },
    ImageControls {
        brightness: f64,
        contrast: f64,
    },
    OptimiseEnabled {
        enabled: bool,
    },
    Message {
        message: WireMessage,
    },
    ControllerFailed {
        reason: String,
    },
    Session {
        state: WireSessionState,
        summary: String,
    },
    Shots {
        shots: Vec<WireShot>,
        group: WireShotStats,
        total_score: f64,
    },
    HoldTrace {
        trace: Option<WireHoldTrace>,
    },
    ReplayCleared,
    PlayerPoint {
        x_mm: f64,
        y_mm: f64,
    },
    PlayerIndex {
        index: usize,
    },
    PlayerProgress {
        fraction: f64,
    },
    PlayerFinished,
    SelectedShot {
        index: usize,
    },
    ReplayLoaded(WireReplay),
    ReplayPlaying {
        playing: bool,
    },
    Sessions {
        sessions: Vec<WireSessionSummary>,
    },
}

impl From<&UiEvent> for WireEvent {
    fn from(event: &UiEvent) -> Self {
        match event {
            UiEvent::Frame(view) => WireEvent::Frame(view.as_ref().into()),
            UiEvent::CameraIdle => WireEvent::CameraIdle,
            UiEvent::AudioLevel(level) => WireEvent::AudioLevel { level: *level },
            UiEvent::TrackingStatusText(text) => {
                WireEvent::TrackingStatusText { text: text.clone() }
            }
            UiEvent::Preferences { prefs, rings } => WireEvent::Preferences {
                prefs: prefs.into(),
                rings: rings.iter().map(WireRing::from).collect(),
            },
            UiEvent::ZeroOffset { active, offset_mm } => WireEvent::ZeroOffset {
                active: *active,
                offset_mm: *offset_mm,
            },
            UiEvent::ClearLiveTrace => WireEvent::ClearLiveTrace,
            UiEvent::DeviceOptions {
                cameras,
                microphones,
                saved_camera,
            } => WireEvent::DeviceOptions {
                cameras: cameras
                    .iter()
                    .map(|(index, name)| WireCamera {
                        index: *index,
                        name: name.clone(),
                    })
                    .collect(),
                microphones: microphones.clone(),
                saved_camera: saved_camera.clone(),
            },
            UiEvent::TargetFaces(faces) => WireEvent::TargetFaces {
                faces: faces.iter().map(WireFace::from).collect(),
            },
            UiEvent::DetectorStatus(message) => WireEvent::DetectorStatus {
                message: message.into(),
            },
            UiEvent::ImageControls {
                brightness,
                contrast,
            } => WireEvent::ImageControls {
                brightness: *brightness,
                contrast: *contrast,
            },
            UiEvent::OptimiseEnabled(enabled) => WireEvent::OptimiseEnabled { enabled: *enabled },
            UiEvent::Message(message) => WireEvent::Message {
                message: message.into(),
            },
            UiEvent::ControllerFailed(reason) => WireEvent::ControllerFailed {
                reason: reason.clone(),
            },
            UiEvent::Session { state, summary } => WireEvent::Session {
                state: (*state).into(),
                summary: summary.clone(),
            },
            UiEvent::Shots(ShotsView {
                shots,
                group,
                total_score,
            }) => WireEvent::Shots {
                shots: shots.iter().map(WireShot::from).collect(),
                group: group.into(),
                total_score: *total_score,
            },
            UiEvent::HoldTrace(trace) => WireEvent::HoldTrace {
                trace: trace.as_ref().map(WireHoldTrace::from),
            },
            UiEvent::ReplayCleared => WireEvent::ReplayCleared,
            UiEvent::Player(PlayerEvent::Point { x_mm, y_mm }) => WireEvent::PlayerPoint {
                x_mm: *x_mm,
                y_mm: *y_mm,
            },
            UiEvent::Player(PlayerEvent::Index(index)) => WireEvent::PlayerIndex { index: *index },
            UiEvent::Player(PlayerEvent::Progress(fraction)) => WireEvent::PlayerProgress {
                fraction: *fraction,
            },
            UiEvent::Player(PlayerEvent::Finished) => WireEvent::PlayerFinished,
            UiEvent::SelectedShot(index) => WireEvent::SelectedShot { index: *index },
            UiEvent::ReplayLoaded(view) => WireEvent::ReplayLoaded(view.into()),
            UiEvent::ReplayPlaying(playing) => WireEvent::ReplayPlaying { playing: *playing },
            UiEvent::Sessions(sessions) => WireEvent::Sessions {
                sessions: sessions.iter().map(WireSessionSummary::from).collect(),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::{Value, json};
    use shottrainer_tracking::frame::{Frame, PixelFormat};

    use super::*;
    use crate::wire::preferences::tests::distinct_preferences;

    fn wire(event: &UiEvent) -> Value {
        serde_json::to_value(WireEvent::from(event)).unwrap()
    }

    #[test]
    fn events_are_tagged_with_their_camel_case_type() {
        assert_eq!(
            wire(&UiEvent::AudioLevel(0.5)),
            json!({"type": "audioLevel", "level": 0.5})
        );
        assert_eq!(wire(&UiEvent::CameraIdle), json!({"type": "cameraIdle"}));
        assert_eq!(
            wire(&UiEvent::ZeroOffset {
                active: true,
                offset_mm: (1.5, -2.0)
            }),
            json!({"type": "zeroOffset", "active": true, "offsetMm": [1.5, -2.0]})
        );
        assert_eq!(
            wire(&UiEvent::ControllerFailed("boom".into())),
            json!({"type": "controllerFailed", "reason": "boom"})
        );
    }

    #[test]
    fn the_remaining_events_keep_their_values() {
        let prefs = distinct_preferences();
        let cases = [
            (
                UiEvent::TrackingStatusText("Tracking".into()),
                json!({"type": "trackingStatusText", "text": "Tracking"}),
            ),
            (
                UiEvent::Preferences {
                    prefs: prefs.clone(),
                    rings: vec![TargetRing {
                        diameter_mm: 30.5,
                        label: None,
                    }],
                },
                json!({
                    "type": "preferences",
                    "prefs": WirePreferences::from(&prefs),
                    "rings": [{"diameterMm": 30.5, "label": null}]
                }),
            ),
            (UiEvent::ClearLiveTrace, json!({"type": "clearLiveTrace"})),
            (
                UiEvent::DetectorStatus(StatusMessage::warning("Lost", 0)),
                json!({"type": "detectorStatus", "message": {"text": "Lost", "severity": "warning", "durationMs": 0}}),
            ),
            (
                UiEvent::ImageControls {
                    brightness: 12.0,
                    contrast: 1.5,
                },
                json!({"type": "imageControls", "brightness": 12.0, "contrast": 1.5}),
            ),
            (
                UiEvent::OptimiseEnabled(true),
                json!({"type": "optimiseEnabled", "enabled": true}),
            ),
            (UiEvent::ReplayCleared, json!({"type": "replayCleared"})),
            (
                UiEvent::SelectedShot(5),
                json!({"type": "selectedShot", "index": 5}),
            ),
            (
                UiEvent::ReplayPlaying(true),
                json!({"type": "replayPlaying", "playing": true}),
            ),
        ];
        for (event, expected) in cases {
            assert_eq!(wire(&event), expected);
        }
    }

    #[test]
    fn a_number_that_is_not_finite_becomes_null() {
        assert_eq!(
            wire(&UiEvent::AudioLevel(f64::NAN)),
            json!({"type": "audioLevel", "level": null})
        );
    }

    #[test]
    fn session_states_carry_their_session_id() {
        let event = |state| UiEvent::Session {
            state,
            summary: "S".into(),
        };
        assert_eq!(
            wire(&event(SessionState::Idle))["state"],
            json!({"kind": "idle"})
        );
        assert_eq!(
            wire(&event(SessionState::Recording(4)))["state"],
            json!({"kind": "recording", "sessionId": 4})
        );
        assert_eq!(
            wire(&event(SessionState::Reviewing(5)))["state"],
            json!({"kind": "reviewing", "sessionId": 5})
        );
    }

    #[test]
    fn player_events_are_flattened() {
        assert_eq!(
            wire(&UiEvent::Player(PlayerEvent::Point {
                x_mm: 1.0,
                y_mm: 2.0
            })),
            json!({"type": "playerPoint", "xMm": 1.0, "yMm": 2.0})
        );
        assert_eq!(
            wire(&UiEvent::Player(PlayerEvent::Index(3))),
            json!({"type": "playerIndex", "index": 3})
        );
        assert_eq!(
            wire(&UiEvent::Player(PlayerEvent::Progress(0.5))),
            json!({"type": "playerProgress", "fraction": 0.5})
        );
        assert_eq!(
            wire(&UiEvent::Player(PlayerEvent::Finished)),
            json!({"type": "playerFinished"})
        );
    }

    #[test]
    fn a_frame_event_carries_the_overlay_without_pixels() {
        let view = FrameView {
            frame: Frame::filled(4, 3, PixelFormat::Grey, 9).unwrap(),
            timestamp: 1.25,
            frame_id: 12,
            status: TrackingStatus::Rejected,
            aim: Some(Marker {
                x_px: 1.0,
                y_px: 2.0,
                radius_px: 3.0,
            }),
            rejected: None,
            zero_px: Some((0.5, 0.75)),
            trace_point_mm: Some((-1.0, 4.0)),
        };
        assert_eq!(
            wire(&UiEvent::Frame(Box::new(view))),
            json!({
                "type": "frame",
                "frameId": 12,
                "timestamp": 1.25,
                "width": 4,
                "height": 3,
                "status": "rejected",
                "aim": {"xPx": 1.0, "yPx": 2.0, "radiusPx": 3.0},
                "rejected": null,
                "zeroPx": [0.5, 0.75],
                "tracePointMm": [-1.0, 4.0]
            })
        );
    }

    #[test]
    fn messages_carry_their_severity() {
        for (message, severity) in [
            (StatusMessage::info("a", 1000), "info"),
            (StatusMessage::warning("b", 2000), "warning"),
            (StatusMessage::success("c", 3000), "success"),
        ] {
            let value = wire(&UiEvent::Message(message.clone()));
            assert_eq!(
                value,
                json!({"type": "message", "message": {"text": message.text, "severity": severity, "durationMs": message.duration_ms}})
            );
        }
    }

    #[test]
    fn shots_carry_the_list_and_the_group() {
        let view = ShotsView {
            shots: vec![ShotEntry {
                timestamp: 3.5,
                x_mm: Some(1.0),
                y_mm: None,
                score: Some("10".into()),
                shot_id: Some(6),
            }],
            group: ShotStats {
                count: 1,
                mean_x_mm: 1.0,
                mean_y_mm: 2.0,
                extreme_spread_mm: 3.0,
                mean_radius_mm: 4.0,
            },
            total_score: 10.0,
        };
        assert_eq!(
            wire(&UiEvent::Shots(view)),
            json!({
                "type": "shots",
                "shots": [{"timestamp": 3.5, "xMm": 1.0, "yMm": null, "score": "10", "shotId": 6}],
                "group": {"count": 1, "meanXMm": 1.0, "meanYMm": 2.0, "extremeSpreadMm": 3.0, "meanRadiusMm": 4.0},
                "totalScore": 10.0
            })
        );
    }

    #[test]
    fn hold_trace_and_replay_keep_their_numbers_apart() {
        let trace = HoldTrace {
            points: vec![(1.0, 2.0)],
            stats: TraceStats {
                samples: 1,
                hold_tremor_mm: 0.1,
                trace_length_mm: 0.2,
                mean_x_mm: 0.3,
                mean_y_mm: 0.4,
            },
        };
        assert_eq!(
            wire(&UiEvent::HoldTrace(Some(trace))),
            json!({
                "type": "holdTrace",
                "trace": {
                    "points": [[1.0, 2.0]],
                    "stats": {"samples": 1, "holdTremorMm": 0.1, "traceLengthMm": 0.2, "meanXMm": 0.3, "meanYMm": 0.4}
                }
            })
        );
        assert_eq!(
            wire(&UiEvent::HoldTrace(None)),
            json!({"type": "holdTrace", "trace": null})
        );
        let replay = ReplayView {
            index: 2,
            points: vec![(0.0, 1.0)],
            release_index: Some(3),
            split_index: Some(4),
            duration_ms: Some(1500),
            hold_zone: Some(HoldZone {
                centre_mm: (0.5, -0.5),
                radius_mm: 1.5,
            }),
            enabled: true,
        };
        assert_eq!(
            wire(&UiEvent::ReplayLoaded(replay)),
            json!({
                "type": "replayLoaded",
                "index": 2,
                "points": [[0.0, 1.0]],
                "releaseIndex": 3,
                "splitIndex": 4,
                "durationMs": 1500,
                "holdZone": {"centreMm": [0.5, -0.5], "radiusMm": 1.5},
                "enabled": true
            })
        );
    }

    #[test]
    fn faces_and_rings_keep_their_fields() {
        let face = TargetFace {
            key: "k".into(),
            label: "Label".into(),
            rings: vec![TargetRing {
                diameter_mm: 45.5,
                label: Some("1".into()),
            }],
            shot_diameter_mm: Some(4.5),
            face_diameter_mm: None,
            scoring_direction: "outward".into(),
        };
        assert_eq!(
            wire(&UiEvent::TargetFaces(vec![face])),
            json!({
                "type": "targetFaces",
                "faces": [{
                    "key": "k",
                    "label": "Label",
                    "rings": [{"diameterMm": 45.5, "label": "1"}],
                    "shotDiameterMm": 4.5,
                    "faceDiameterMm": null,
                    "scoringDirection": "outward"
                }]
            })
        );
    }

    #[test]
    fn device_options_list_cameras_by_index_and_name() {
        assert_eq!(
            wire(&UiEvent::DeviceOptions {
                cameras: vec![(0, "Built-in".into()), (3, "USB".into())],
                microphones: vec!["default".into()],
                saved_camera: "USB".into(),
            }),
            json!({
                "type": "deviceOptions",
                "cameras": [{"index": 0, "name": "Built-in"}, {"index": 3, "name": "USB"}],
                "microphones": ["default"],
                "savedCamera": "USB"
            })
        );
    }

    #[test]
    fn session_times_are_iso_local_times() {
        let summary = SessionSummary {
            id: 1,
            name: "S".into(),
            started_at: Default::default(),
            ended_at: None,
            shot_count: 2,
            total_score: 19.5,
            category: "practice".into(),
        };
        assert_eq!(
            wire(&UiEvent::Sessions(vec![summary])),
            json!({
                "type": "sessions",
                "sessions": [{
                    "id": 1,
                    "name": "S",
                    "startedAt": "1970-01-01T00:00:00",
                    "endedAt": null,
                    "shotCount": 2,
                    "totalScore": 19.5,
                    "category": "practice"
                }]
            })
        );
    }
}
