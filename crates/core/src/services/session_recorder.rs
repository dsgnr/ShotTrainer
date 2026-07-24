//! Writes a live session's trace and shots to the database.
//!
//! Samples are batched so the database is not asked to commit a transaction
//! for every frame. A batch flushes once `flush_every` samples are pending or
//! `flush_seconds` of trace time has passed since the last flush.

use shottrainer_tracking::models::TrackingSample;

use crate::sessions::{DatabaseError, NewSession, NewShot, SessionRepository, utc_now};

#[derive(Debug, thiserror::Error)]
pub enum RecorderError {
    #[error("Session already in progress")]
    AlreadyRunning,
    #[error(transparent)]
    Database(#[from] DatabaseError),
}

#[derive(Debug, Clone, PartialEq)]
pub struct RecorderConfig {
    pub flush_every: usize,
    pub flush_seconds: f64,
}

impl Default for RecorderConfig {
    fn default() -> Self {
        RecorderConfig {
            flush_every: 60,
            flush_seconds: 1.0,
        }
    }
}

/// Holds the batching state only. Every method that touches the database
/// takes the repository per call, so the recorder can live beside the
/// connection and move between threads.
pub struct SessionRecorder {
    config: RecorderConfig,
    session_id: Option<i64>,
    pending: Vec<TrackingSample>,
    last_flush_ts: f64,
}

impl SessionRecorder {
    pub fn new(config: RecorderConfig) -> Self {
        SessionRecorder {
            config,
            session_id: None,
            pending: Vec::new(),
            last_flush_ts: 0.0,
        }
    }

    pub fn session_id(&self) -> Option<i64> {
        self.session_id
    }

    pub fn is_recording(&self) -> bool {
        self.session_id.is_some()
    }

    pub fn start(
        &mut self,
        repo: &SessionRepository,
        new: &NewSession,
    ) -> Result<i64, RecorderError> {
        if self.session_id.is_some() {
            return Err(RecorderError::AlreadyRunning);
        }
        let id = repo.create_session(new)?;
        self.session_id = Some(id);
        self.pending.clear();
        self.last_flush_ts = 0.0;
        log::info!("started session {id}");
        Ok(id)
    }

    /// Drops the sample when no session is running.
    pub fn add_sample(
        &mut self,
        repo: &SessionRepository,
        sample: TrackingSample,
    ) -> Result<(), DatabaseError> {
        if self.session_id.is_none() {
            return Ok(());
        }
        let timestamp = sample.timestamp;
        self.pending.push(sample);
        if self.pending.len() >= self.config.flush_every
            || timestamp - self.last_flush_ts >= self.config.flush_seconds
        {
            self.flush(repo, timestamp)?;
        }
        Ok(())
    }

    /// Flushes pending samples first so the saved trace has no gap where the
    /// shot lands. Returns `None` when no session is running.
    pub fn add_shot(
        &mut self,
        repo: &SessionRepository,
        shot: &NewShot,
    ) -> Result<Option<i64>, DatabaseError> {
        let Some(session_id) = self.session_id else {
            return Ok(None);
        };
        self.flush(repo, shot.ts)?;
        repo.add_shot(session_id, shot).map(Some)
    }

    /// Flushes, stamps `ended_at` and returns the session id, or `None` when
    /// no session is running.
    pub fn stop(&mut self, repo: &SessionRepository) -> Result<Option<i64>, DatabaseError> {
        let Some(session_id) = self.session_id else {
            return Ok(None);
        };
        self.flush(repo, self.last_flush_ts)?;
        repo.end_session(session_id, Some(utc_now()))?;
        self.session_id = None;
        log::info!("stopped session {session_id}");
        Ok(Some(session_id))
    }

    /// Keeps the pending samples when the write fails so a retry loses none.
    fn flush(&mut self, repo: &SessionRepository, now_ts: f64) -> Result<(), DatabaseError> {
        let Some(session_id) = self.session_id else {
            return Ok(());
        };
        if self.pending.is_empty() {
            return Ok(());
        }
        repo.append_trace(session_id, &self.pending)?;
        self.pending.clear();
        self.last_flush_ts = now_ts;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn assert_send<T: Send>() {}

    #[test]
    fn recorder_is_send() {
        assert_send::<SessionRecorder>();
    }
}
