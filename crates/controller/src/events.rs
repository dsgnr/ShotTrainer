//! What the controller tells the front end. Every event is plain data, so an
//! interface layer can serialise it in whatever form it needs.

use shottrainer_core::services::shot_stats::{ShotStats, TraceStats};

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

#[derive(Debug, Clone, PartialEq)]
pub enum UiEvent {
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
}
