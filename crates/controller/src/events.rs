//! What the controller tells the front end. Every event is plain data, so an
//! interface layer can serialise it in whatever form it needs.

use shottrainer_core::services::shot_stats::{ShotStats, TraceStats};
use shottrainer_core::sessions::SessionSummary;
use shottrainer_settings::Preferences;
use shottrainer_settings::target_faces::{TargetFace, TargetRing};

use crate::frames::FrameView;
use crate::player::PlayerEvent;
use crate::session::{SessionState, ShotEntry};

/// Receives every [`UiEvent`], in order, on the controller's thread.
pub type UiSink = Box<dyn Fn(UiEvent) + Send + 'static>;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Severity {
    Info,
    Warning,
    Success,
}

/// A transient status line, Python's `statusBar().showMessage(text, ms)`.
#[derive(Debug, Clone, PartialEq)]
pub struct StatusMessage {
    pub text: String,
    pub severity: Severity,
    pub duration_ms: u32,
}

impl StatusMessage {
    pub fn info(text: impl Into<String>, duration_ms: u32) -> Self {
        StatusMessage {
            text: text.into(),
            severity: Severity::Info,
            duration_ms,
        }
    }

    pub fn warning(text: impl Into<String>, duration_ms: u32) -> Self {
        StatusMessage {
            text: text.into(),
            severity: Severity::Warning,
            duration_ms,
        }
    }
}

/// The on-screen shot list with the group figures the hero panel shows.
#[derive(Debug, Clone, PartialEq)]
pub struct ShotsView {
    pub shots: Vec<ShotEntry>,
    /// From the shots with both coordinates.
    pub group: ShotStats,
    pub total_score: f64,
}

/// Mapped trace points up to the shot, for tremor and time on target.
#[derive(Debug, Clone, PartialEq)]
pub struct HoldTrace {
    pub points: Vec<(f64, f64)>,
    pub stats: TraceStats,
}

/// The amber circle at the mean pre-shot position with the tremor radius.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct HoldZone {
    pub centre_mm: (f64, f64),
    pub radius_mm: f64,
}

/// A saved shot's window loaded for replay. The `Player` events that follow
/// position the playhead, so a front end applies this first.
#[derive(Debug, Clone, PartialEq)]
pub struct ReplayView {
    /// The selected shot's position in the shot list.
    pub index: usize,
    pub points: Vec<(f64, f64)>,
    /// Where the release window starts.
    pub release_index: Option<usize>,
    /// The sample nearest the shot.
    pub split_index: Option<usize>,
    /// Recorded time from the first to the last point.
    pub duration_ms: Option<i64>,
    pub hold_zone: Option<HoldZone>,
    /// False when the window holds no samples.
    pub enabled: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub enum UiEvent {
    Frame(Box<FrameView>),
    /// The camera was stopped. The view shows its idle state.
    CameraIdle,
    /// The microphone level multiplied by the gain, for the meter.
    AudioLevel(f64),
    /// The header line, such as `Tracking 60 mm circle - 0.125 mm/px`.
    TrackingStatusText(String),
    /// The active preferences and the rings of the active face.
    Preferences {
        prefs: Preferences,
        rings: Vec<TargetRing>,
    },
    ZeroOffset {
        active: bool,
        offset_mm: (f64, f64),
    },
    /// Clears the live target trace and the hold zone.
    ClearLiveTrace,
    DeviceOptions {
        cameras: Vec<(i64, String)>,
        microphones: Vec<String>,
        /// The saved camera name, so the dialog can preselect it.
        saved_camera: String,
    },
    TargetFaces(Vec<TargetFace>),
    Message(StatusMessage),
    /// The header state and the summary line under the session controls.
    Session {
        state: SessionState,
        summary: String,
    },
    Shots(ShotsView),
    /// `None` clears the hold figures.
    HoldTrace(Option<HoldTrace>),
    /// The replay trace was unloaded. The replay controls are disabled and
    /// stopped, and the target trace, segments, isolation and hold zone are
    /// cleared.
    ReplayCleared,
    Player(PlayerEvent),
    /// Highlights a shot on the target, whether or not a replay follows.
    SelectedShot(usize),
    ReplayLoaded(ReplayView),
    /// The play or pause glyph of the replay controls.
    ReplayPlaying(bool),
    /// The session browser list, newest first.
    Sessions(Vec<SessionSummary>),
}
