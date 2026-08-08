//! Camera capture thread. The device is reached through [`FrameSource`], so
//! the lifecycle is tested without hardware and the OpenCV device lives in
//! the feature-gated `cv` module.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::thread::JoinHandle;
use std::time::Duration;

use crate::frame::Frame;

/// Seconds on the shared monotonic timeline, supplied by the caller.
pub type ClockFn = Arc<dyn Fn() -> f64 + Send + Sync>;

/// Python `CameraConfig`. `width`, `height` and `fps` are requests the device
/// may round. `None` or zero leaves the device default.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct CameraConfig {
    pub device_index: i32,
    pub width: Option<u32>,
    pub height: Option<u32>,
    pub fps: Option<f64>,
    /// An OpenCV `VideoCaptureAPIs` value. 0 lets OpenCV choose.
    pub api_preference: i32,
}

#[derive(Debug, Clone, PartialEq)]
pub enum CameraEvent {
    Opened {
        width: u32,
        height: u32,
        fps: f64,
    },
    Frame {
        frame: Frame,
        timestamp: f64,
        frame_id: i64,
    },
    Error(String),
    Closed,
}

/// An open device. Created and used only on the capture thread.
pub trait FrameSource {
    /// Blocks until the next frame. `None` is a failed read.
    fn read(&mut self) -> Option<Frame>;
}

pub struct OpenedSource {
    pub source: Box<dyn FrameSource>,
    pub width: u32,
    pub height: u32,
    pub fps: f64,
}

/// Opens the device on the capture thread. The error text is emitted as
/// [`CameraEvent::Error`].
pub type SourceOpener = Box<dyn FnOnce() -> Result<OpenedSource, String> + Send>;

pub type EventSink = Box<dyn Fn(CameraEvent) + Send + Sync + 'static>;

#[derive(Debug, Clone, PartialEq)]
pub struct CaptureOptions {
    /// Consecutive failed reads tolerated before giving up. Python uses 30.
    pub max_consecutive_failures: u32,
    /// Pause after a failed read so a dead device does not spin a core.
    pub failure_backoff: Duration,
    /// How long `stop` waits for the thread before detaching it.
    pub stop_timeout: Duration,
}

impl Default for CaptureOptions {
    fn default() -> Self {
        CaptureOptions {
            max_consecutive_failures: 30,
            failure_backoff: Duration::from_millis(20),
            stop_timeout: Duration::from_secs(5),
        }
    }
}

/// A running capture thread. Single use, as in Python.
pub struct CameraCapture {
    running: Arc<AtomicBool>,
    done: Option<mpsc::Receiver<()>>,
    thread: Option<JoinHandle<()>>,
    stop_timeout: Duration,
}

impl CameraCapture {
    /// Spawns the capture thread and returns at once, because opening can
    /// block while the operating system asks for camera permission.
    ///
    /// Events arrive on the capture thread. A failed open yields one `Error`
    /// and nothing else. Otherwise `Opened` comes first, then frames with ids
    /// counting from 1 and the clock read just after each read returned, an
    /// optional `Error` when the device stops producing frames, and `Closed`
    /// after the device is released. `Closed` is sent at most once, and
    /// exactly once unless an event callback panics.
    ///
    /// If `stop` was requested while the opener was still blocked, a device
    /// that then opens is released with `Closed` and no `Opened`, and an open
    /// that then fails emits nothing. If the thread cannot be spawned the
    /// `Error` is delivered on the caller's thread.
    pub fn start_with(
        opener: SourceOpener,
        options: CaptureOptions,
        clock: ClockFn,
        on_event: EventSink,
    ) -> CameraCapture {
        let on_event: Arc<dyn Fn(CameraEvent) + Send + Sync> = Arc::from(on_event);
        let running = Arc::new(AtomicBool::new(true));
        let (done_tx, done_rx) = mpsc::channel::<()>();
        let spawned = {
            let (on_event, running) = (on_event.clone(), running.clone());
            let options = options.clone();
            std::thread::Builder::new()
                .name("camera-capture".to_owned())
                .spawn(move || {
                    // Dropped on every exit path, including a panic in a callback.
                    let _done = done_tx;
                    run(opener, &options, &clock, &*on_event, &running);
                })
        };
        let thread = match spawned {
            Ok(handle) => Some(handle),
            Err(error) => {
                on_event(CameraEvent::Error(format!(
                    "Could not start the camera thread: {error}"
                )));
                None
            }
        };
        CameraCapture {
            running,
            done: Some(done_rx),
            thread,
            stop_timeout: options.stop_timeout,
        }
    }

    /// Asks the thread to finish and waits up to the stop timeout. A thread
    /// still blocked in a device read after that is detached with a warning
    /// and emits `Closed` when the read returns. Safe to call repeatedly.
    pub fn stop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        let Some(thread) = self.thread.take() else {
            return;
        };
        let done = self.done.take();
        match done.map(|rx| rx.recv_timeout(self.stop_timeout)) {
            Some(Err(RecvTimeoutError::Timeout)) => {
                log::warn!(
                    "Camera thread did not stop within {:?}, detaching it",
                    self.stop_timeout
                );
            }
            _ => {
                if thread.join().is_err() {
                    log::error!("camera capture thread panicked");
                }
            }
        }
    }
}

impl Drop for CameraCapture {
    fn drop(&mut self) {
        self.stop();
    }
}

fn run(
    opener: SourceOpener,
    options: &CaptureOptions,
    clock: &ClockFn,
    on_event: &dyn Fn(CameraEvent),
    running: &AtomicBool,
) {
    let opened = match opener() {
        Ok(opened) => opened,
        Err(message) => {
            if running.load(Ordering::SeqCst) {
                on_event(CameraEvent::Error(message));
            }
            return;
        }
    };
    if !running.load(Ordering::SeqCst) {
        drop(opened.source);
        on_event(CameraEvent::Closed);
        return;
    }
    on_event(CameraEvent::Opened {
        width: opened.width,
        height: opened.height,
        fps: opened.fps,
    });
    let mut source = opened.source;
    let mut failures = 0_u32;
    let mut frame_id = 0_i64;
    while running.load(Ordering::SeqCst) {
        let frame = source.read();
        let timestamp = clock();
        if !running.load(Ordering::SeqCst) {
            // A read that returns after `stop` is dropped, so no frame follows a stop request.
            break;
        }
        match frame {
            Some(frame) if !frame.is_empty() => {
                failures = 0;
                frame_id += 1;
                on_event(CameraEvent::Frame {
                    frame,
                    timestamp,
                    frame_id,
                });
            }
            _ => {
                failures += 1;
                if failures > options.max_consecutive_failures {
                    on_event(CameraEvent::Error("Camera produced no frames".to_owned()));
                    break;
                }
                std::thread::sleep(options.failure_backoff);
            }
        }
    }
    drop(source);
    on_event(CameraEvent::Closed);
}

#[cfg(test)]
mod tests {
    use std::sync::Mutex;
    use std::sync::mpsc::Receiver;
    use std::time::Instant;

    use super::*;
    use crate::frame::PixelFormat;

    /// Plays back a script of reads, then fails every read.
    struct Script(std::vec::IntoIter<Option<Frame>>);

    impl FrameSource for Script {
        fn read(&mut self) -> Option<Frame> {
            self.0.next().flatten()
        }
    }

    /// A read that takes `delay` and then returns a frame. `started` is
    /// signalled as each read begins.
    struct Slow {
        delay: Duration,
        started: Option<mpsc::Sender<()>>,
    }

    impl Slow {
        fn new(delay: Duration) -> Self {
            Slow {
                delay,
                started: None,
            }
        }
    }

    impl FrameSource for Slow {
        fn read(&mut self) -> Option<Frame> {
            if let Some(started) = &self.started {
                let _ = started.send(());
            }
            std::thread::sleep(self.delay);
            Some(frame())
        }
    }

    fn frame() -> Frame {
        Frame::filled(2, 2, PixelFormat::Grey, 7).unwrap()
    }

    fn fast() -> CaptureOptions {
        CaptureOptions {
            max_consecutive_failures: 3,
            failure_backoff: Duration::from_millis(1),
            stop_timeout: Duration::from_secs(5),
        }
    }

    /// A clock that returns 1.0, 2.0, 3.0 and so on.
    fn counting_clock() -> ClockFn {
        let next = Mutex::new(0.0);
        Arc::new(move || {
            let mut t = next.lock().unwrap();
            *t += 1.0;
            *t
        })
    }

    fn opener(source: impl FrameSource + Send + 'static) -> SourceOpener {
        Box::new(move || {
            Ok(OpenedSource {
                source: Box::new(source),
                width: 2,
                height: 2,
                fps: 30.0,
            })
        })
    }

    fn start(
        opener: SourceOpener,
        options: CaptureOptions,
    ) -> (CameraCapture, Receiver<CameraEvent>) {
        let (tx, rx) = mpsc::channel();
        let sink: EventSink = Box::new(move |event| {
            let _ = tx.send(event);
        });
        (
            CameraCapture::start_with(opener, options, counting_clock(), sink),
            rx,
        )
    }

    /// Collects events until `Closed` or a bounded wait runs out.
    fn until_closed(rx: &Receiver<CameraEvent>) -> Vec<CameraEvent> {
        let mut events = Vec::new();
        while let Ok(event) = rx.recv_timeout(Duration::from_secs(5)) {
            let closed = event == CameraEvent::Closed;
            events.push(event);
            if closed {
                return events;
            }
        }
        panic!("no Closed event, got {events:?}");
    }

    #[test]
    fn frames_carry_ids_and_clock_readings_then_a_dead_device_closes() {
        let script = Script(vec![Some(frame()), None, Some(frame())].into_iter());
        let (mut capture, rx) = start(opener(script), fast());
        let events = until_closed(&rx);
        assert_eq!(
            events,
            vec![
                CameraEvent::Opened {
                    width: 2,
                    height: 2,
                    fps: 30.0
                },
                CameraEvent::Frame {
                    frame: frame(),
                    timestamp: 1.0,
                    frame_id: 1
                },
                CameraEvent::Frame {
                    frame: frame(),
                    timestamp: 3.0,
                    frame_id: 2
                },
                CameraEvent::Error("Camera produced no frames".to_owned()),
                CameraEvent::Closed,
            ]
        );
        capture.stop();
        capture.stop();
    }

    #[test]
    fn a_good_frame_resets_the_failure_count() {
        let mut reads = Vec::new();
        for _ in 0..4 {
            reads.extend([None, None, None, Some(frame())]);
        }
        let (_capture, rx) = start(opener(Script(reads.into_iter())), fast());
        let events = until_closed(&rx);
        let frames = events
            .iter()
            .filter(|e| matches!(e, CameraEvent::Frame { .. }))
            .count();
        assert_eq!(frames, 4);
    }

    #[test]
    fn empty_frames_count_as_failed_reads() {
        let empty = Frame::filled(0, 0, PixelFormat::Bgr, 0).unwrap();
        let script = Script(vec![Some(empty.clone()); 10].into_iter());
        let (_capture, rx) = start(opener(script), fast());
        let events = until_closed(&rx);
        assert!(
            !events
                .iter()
                .any(|e| matches!(e, CameraEvent::Frame { .. }))
        );
        assert!(events.contains(&CameraEvent::Error("Camera produced no frames".to_owned())));
    }

    #[test]
    fn a_failed_open_emits_one_error_and_nothing_else() {
        let failing: SourceOpener = Box::new(|| Err("Could not open camera 3".to_owned()));
        let (mut capture, rx) = start(failing, fast());
        let events = until_finished(&rx);
        capture.stop();
        capture.stop();
        assert_eq!(
            events,
            vec![CameraEvent::Error("Could not open camera 3".to_owned())]
        );
    }

    #[test]
    fn stop_ends_streaming_with_one_closed_and_no_later_frames() {
        let (mut capture, rx) = start(opener(Slow::new(Duration::from_millis(5))), fast());
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(5)),
            Ok(CameraEvent::Opened { .. })
        ));
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(5)),
            Ok(CameraEvent::Frame { .. })
        ));
        capture.stop();
        let rest: Vec<_> = rx.try_iter().collect();
        assert_eq!(rest.last(), Some(&CameraEvent::Closed));
        assert_eq!(
            rest.iter().filter(|e| **e == CameraEvent::Closed).count(),
            1
        );
        capture.stop();
        assert!(rx.try_recv().is_err());
    }

    /// Collects events until the sink is dropped, which happens when the
    /// capture thread has finished.
    fn until_finished(rx: &Receiver<CameraEvent>) -> Vec<CameraEvent> {
        let mut events = Vec::new();
        loop {
            match rx.recv_timeout(Duration::from_secs(5)) {
                Ok(event) => events.push(event),
                Err(mpsc::RecvTimeoutError::Disconnected) => return events,
                Err(mpsc::RecvTimeoutError::Timeout) => panic!("thread did not finish"),
            }
        }
    }

    /// An opener that blocks until released, then opens an idle device or
    /// fails with the given message.
    fn blocked_opener(release: Receiver<()>, failure: Option<&'static str>) -> SourceOpener {
        Box::new(move || {
            release.recv().unwrap();
            match failure {
                Some(message) => Err(message.to_owned()),
                None => Ok(OpenedSource {
                    source: Box::new(Script(Vec::new().into_iter())),
                    width: 2,
                    height: 2,
                    fps: 30.0,
                }),
            }
        })
    }

    fn short_stop() -> CaptureOptions {
        CaptureOptions {
            stop_timeout: Duration::from_millis(50),
            ..fast()
        }
    }

    #[test]
    fn a_device_that_opens_after_stop_is_released_without_opened() {
        let (release_tx, release_rx) = mpsc::channel();
        let (mut capture, rx) = start(blocked_opener(release_rx, None), short_stop());
        capture.stop();
        release_tx.send(()).unwrap();
        assert_eq!(until_finished(&rx), vec![CameraEvent::Closed]);
    }

    #[test]
    fn an_open_that_fails_after_stop_emits_nothing() {
        let (release_tx, release_rx) = mpsc::channel();
        let (mut capture, rx) = start(
            blocked_opener(release_rx, Some("late failure")),
            short_stop(),
        );
        capture.stop();
        release_tx.send(()).unwrap();
        assert_eq!(until_finished(&rx), Vec::new());
    }

    #[test]
    fn dropping_the_handle_stops_the_thread() {
        let (capture, rx) = start(opener(Slow::new(Duration::from_millis(5))), fast());
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(5)),
            Ok(CameraEvent::Opened { .. })
        ));
        drop(capture);
        assert_eq!(rx.try_iter().last(), Some(CameraEvent::Closed));
    }

    #[test]
    fn a_stalled_read_does_not_hold_stop_past_the_timeout() {
        let options = CaptureOptions {
            stop_timeout: Duration::from_millis(100),
            ..fast()
        };
        let (started_tx, started_rx) = mpsc::channel();
        let slow = Slow {
            delay: Duration::from_millis(1500),
            started: Some(started_tx),
        };
        let (mut capture, rx) = start(opener(slow), options);
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(5)),
            Ok(CameraEvent::Opened { .. })
        ));
        started_rx.recv_timeout(Duration::from_secs(5)).unwrap();
        let started = Instant::now();
        capture.stop();
        assert!(
            started.elapsed() < Duration::from_millis(1000),
            "stop took {:?}",
            started.elapsed()
        );
        // The detached thread still releases the device and reports it, without a late frame.
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(5)),
            Ok(CameraEvent::Closed)
        );
    }
}
