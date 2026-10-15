//! Writes a live session's trace and shots to the database.
//!
//! Samples are batched so the database is not asked to commit a transaction
//! for every frame. A batch flushes once `flush_every` samples are pending or
//! `flush_seconds` of trace time has passed since the last flush. After a
//! failed write the batch is retried at most once per `flush_seconds`, and the
//! pending samples are capped at `MAX_PENDING` so a broken database cannot grow
//! memory without limit.

use std::collections::VecDeque;

use shottrainer_tracking::models::TrackingSample;

use crate::sessions::{DatabaseError, NewSession, NewShot, SessionRepository, utc_now};

/// About two minutes of trace at 30 frames per second.
const MAX_PENDING: usize = 3600;

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
    pending: VecDeque<TrackingSample>,
    last_flush_ts: f64,
    last_failed_ts: Option<f64>,
}

impl SessionRecorder {
    pub fn new(config: RecorderConfig) -> Self {
        SessionRecorder {
            config,
            session_id: None,
            pending: VecDeque::new(),
            last_flush_ts: 0.0,
            last_failed_ts: None,
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
        self.last_failed_ts = None;
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
        self.pending.push_back(sample);
        if self.pending.len() > MAX_PENDING {
            self.pending.pop_front();
        }
        if self
            .last_failed_ts
            .is_some_and(|failed| timestamp - failed < self.config.flush_seconds)
        {
            return Ok(());
        }
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

    /// Saves pending trace samples for review without ending the recording.
    pub fn flush_pending(&mut self, repo: &SessionRepository) -> Result<(), DatabaseError> {
        let timestamp = self
            .pending
            .back()
            .map_or(self.last_flush_ts, |sample| sample.timestamp);
        self.flush(repo, timestamp)
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
    /// `add_sample` backs off after a failure. The other callers always try.
    fn flush(&mut self, repo: &SessionRepository, now_ts: f64) -> Result<(), DatabaseError> {
        let Some(session_id) = self.session_id else {
            return Ok(());
        };
        if self.pending.is_empty() {
            return Ok(());
        }
        if let Err(error) = repo.append_trace(session_id, self.pending.make_contiguous()) {
            self.last_failed_ts = Some(now_ts);
            return Err(error);
        }
        self.pending.clear();
        self.last_flush_ts = now_ts;
        self.last_failed_ts = None;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    use crate::sessions::{init_database, make_engine};

    fn assert_send<T: Send>() {}

    fn sample(ts: f64) -> TrackingSample {
        TrackingSample::new(ts, 0.0, 0.0)
    }

    #[test]
    fn recorder_is_send() {
        assert_send::<SessionRecorder>();
    }

    #[test]
    fn a_failed_write_is_retried_once_per_interval_and_stays_bounded() {
        let db = make_engine(":memory:").unwrap();
        init_database(&db).unwrap();
        let repo = SessionRepository::new(&db);
        let mut recorder = SessionRecorder::new(RecorderConfig {
            flush_every: 1,
            flush_seconds: 1.0,
        });
        let id = recorder.start(&repo, &NewSession::default()).unwrap();
        db.execute_batch("CREATE TRIGGER reject_trace BEFORE INSERT ON trace_samples BEGIN SELECT RAISE(ABORT, 'test failure'); END;").unwrap();

        assert!(recorder.add_sample(&repo, sample(0.1)).is_err());
        // Inside the back-off window no write is attempted, so no error is raised.
        assert!(recorder.add_sample(&repo, sample(0.2)).is_ok());
        assert_eq!(recorder.pending.len(), 2);

        for i in 0..MAX_PENDING + 10 {
            recorder
                .add_sample(&repo, sample(0.3 + i as f64 * 1e-6))
                .unwrap();
        }
        assert_eq!(recorder.pending.len(), MAX_PENDING);

        db.execute_batch("DROP TRIGGER reject_trace").unwrap();
        recorder.add_sample(&repo, sample(1.2)).unwrap();
        assert!(recorder.pending.is_empty());
        assert_eq!(repo.trace_count(id).unwrap(), MAX_PENDING as i64);
    }
}
