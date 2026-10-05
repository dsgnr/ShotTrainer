//! Camera and microphone access. On macOS the system prompts are requested
//! on the main thread before the controller opens any device, and the
//! controller starts once both are answered.

use std::sync::{Arc, Mutex, PoisonError};

type StartFn = Box<dyn FnOnce() + Send>;

/// Runs `start` once, after the last of a fixed number of answers.
pub struct StartGate {
    remaining: Mutex<usize>,
    start: Mutex<Option<StartFn>>,
}

impl StartGate {
    /// With no requests `start` runs before this returns.
    pub fn new(requests: usize, start: impl FnOnce() + Send + 'static) -> Arc<Self> {
        let gate = Arc::new(StartGate {
            remaining: Mutex::new(requests),
            start: Mutex::new(Some(Box::new(start))),
        });
        if requests == 0 {
            gate.run();
        }
        gate
    }

    /// One request was answered. Answers beyond the expected number are
    /// ignored.
    pub fn answered(&self) {
        let last = {
            let mut remaining = self
                .remaining
                .lock()
                .unwrap_or_else(PoisonError::into_inner);
            let last = *remaining == 1;
            *remaining = remaining.saturating_sub(1);
            last
        };
        if last {
            self.run();
        }
    }

    fn run(&self) {
        let start = self
            .start
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .take();
        if let Some(start) = start {
            start();
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Media {
    Camera,
    Microphone,
}

impl Media {
    pub fn name(self) -> &'static str {
        match self {
            Media::Camera => "camera",
            Media::Microphone => "microphone",
        }
    }
}

#[cfg(target_os = "macos")]
#[allow(unsafe_code)]
pub mod macos {
    use std::sync::{Mutex, PoisonError};

    use block2::RcBlock;
    use objc2::runtime::Bool;
    use objc2_av_foundation::{
        AVAuthorizationStatus, AVCaptureDevice, AVMediaType, AVMediaTypeAudio, AVMediaTypeVideo,
    };

    use super::Media;

    fn media_type(media: Media) -> Option<&'static AVMediaType> {
        // SAFETY: AVFoundation's media type constants are initialised before
        // `main` and never written.
        unsafe {
            match media {
                Media::Camera => AVMediaTypeVideo,
                Media::Microphone => AVMediaTypeAudio,
            }
        }
    }

    /// Shows the system prompt if the user has not answered it before, and
    /// calls `answered` with the outcome on an arbitrary thread. Without a
    /// prompt `answered` runs before this returns. Call it on the main
    /// thread.
    pub fn request_access(media: Media, answered: impl FnOnce(bool) + Send + 'static) {
        let Some(media_type) = media_type(media) else {
            answered(false);
            return;
        };
        // SAFETY: the media type is video or audio, the only values the
        // method accepts without raising.
        let status = unsafe { AVCaptureDevice::authorizationStatusForMediaType(media_type) };
        if status != AVAuthorizationStatus::NotDetermined {
            answered(status == AVAuthorizationStatus::Authorized);
            return;
        }
        let answered = Mutex::new(Some(answered));
        let handler = RcBlock::new(move |granted: Bool| {
            let answered = answered
                .lock()
                .unwrap_or_else(PoisonError::into_inner)
                .take();
            if let Some(answered) = answered {
                answered(granted.as_bool());
            }
        });
        // SAFETY: as above. AVFoundation copies the block before returning.
        unsafe {
            AVCaptureDevice::requestAccessForMediaType_completionHandler(media_type, &handler);
        }
    }
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicUsize, Ordering};

    use super::*;

    fn counter() -> (Arc<AtomicUsize>, impl FnOnce() + Send + 'static) {
        let runs = Arc::new(AtomicUsize::new(0));
        let start = {
            let runs = runs.clone();
            move || {
                runs.fetch_add(1, Ordering::SeqCst);
            }
        };
        (runs, start)
    }

    #[test]
    fn starts_only_after_the_last_answer() {
        let (runs, start) = counter();
        let gate = StartGate::new(2, start);
        assert_eq!(runs.load(Ordering::SeqCst), 0);
        gate.answered();
        assert_eq!(runs.load(Ordering::SeqCst), 0);
        gate.answered();
        assert_eq!(runs.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn starts_at_once_without_requests() {
        let (runs, start) = counter();
        let _gate = StartGate::new(0, start);
        assert_eq!(runs.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn extra_answers_do_not_start_again() {
        let (runs, start) = counter();
        let gate = StartGate::new(1, start);
        gate.answered();
        gate.answered();
        gate.answered();
        assert_eq!(runs.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn answers_from_other_threads_start_once() {
        let (runs, start) = counter();
        let gate = StartGate::new(2, start);
        let threads: Vec<_> = (0..2)
            .map(|_| {
                let gate = gate.clone();
                std::thread::spawn(move || gate.answered())
            })
            .collect();
        for thread in threads {
            thread.join().unwrap();
        }
        assert_eq!(runs.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn media_names_match_the_status_report() {
        assert_eq!(Media::Camera.name(), "camera");
        assert_eq!(Media::Microphone.name(), "microphone");
    }
}
