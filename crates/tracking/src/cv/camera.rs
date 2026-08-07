//! OpenCV `VideoCapture` behind [`FrameSource`].

use opencv::core::Mat;
use opencv::prelude::*;
use opencv::videoio::{self, VideoCapture};

use super::mat::mat_to_frame;
use crate::capture::{
    CameraCapture, CameraConfig, CaptureOptions, ClockFn, EventSink, FrameSource, OpenedSource,
};
use crate::frame::Frame;

struct OpenCvSource {
    capture: VideoCapture,
    buffer: Mat,
}

impl FrameSource for OpenCvSource {
    fn read(&mut self) -> Option<Frame> {
        match self.capture.read(&mut self.buffer) {
            Ok(true) if !self.buffer.empty() => mat_to_frame(&self.buffer)
                .inspect_err(|error| log::debug!("Dropped camera frame: {error}"))
                .ok(),
            Ok(_) => None,
            Err(error) => {
                log::debug!("Camera read failed: {error}");
                None
            }
        }
    }
}

/// Opens the device and applies the requested mode. Runs on the capture thread.
pub fn open_camera(config: &CameraConfig) -> Result<OpenedSource, String> {
    let failed = || format!("Could not open camera {}", config.device_index);
    let mut capture =
        VideoCapture::new(config.device_index, config.api_preference).map_err(|_| failed())?;
    if !capture.is_opened().unwrap_or(false) {
        return Err(failed());
    }
    let requests = [
        (videoio::CAP_PROP_FRAME_WIDTH, config.width.map(f64::from)),
        (videoio::CAP_PROP_FRAME_HEIGHT, config.height.map(f64::from)),
        (videoio::CAP_PROP_FPS, config.fps),
    ];
    for (property, value) in requests {
        if let Some(value) = value.filter(|v| *v > 0.0) {
            // A refused request leaves the device default, as in Python.
            let _ = capture.set(property, value);
        }
    }
    let get = |property| {
        capture
            .get(property)
            .ok()
            .filter(|v| v.is_finite())
            .unwrap_or(0.0)
    };
    let (width, height, fps) = (
        get(videoio::CAP_PROP_FRAME_WIDTH) as u32,
        get(videoio::CAP_PROP_FRAME_HEIGHT) as u32,
        get(videoio::CAP_PROP_FPS),
    );
    Ok(OpenedSource {
        source: Box::new(OpenCvSource {
            capture,
            buffer: Mat::default(),
        }),
        width,
        height,
        fps,
    })
}

impl CameraCapture {
    /// Opens `config` through OpenCV on the capture thread.
    pub fn start(config: CameraConfig, clock: ClockFn, on_event: EventSink) -> CameraCapture {
        CameraCapture::start_with(
            Box::new(move || open_camera(&config)),
            CaptureOptions::default(),
            clock,
            on_event,
        )
    }
}

/// Probes OpenCV indices `0..max_index` and names them `Camera {index}`, as
/// the Python fallback does. Each probe opens the device, so this is slow on
/// macOS and may trigger the permission prompt.
pub fn probe_cameras(max_index: i32) -> Vec<(i32, String)> {
    (0..max_index.max(0))
        .filter(|&index| {
            VideoCapture::new(index, videoio::CAP_ANY)
                .and_then(|mut capture| {
                    let opened = capture.is_opened()?;
                    capture.release()?;
                    Ok(opened)
                })
                .unwrap_or(false)
        })
        .map(|index| (index, format!("Camera {index}")))
        .collect()
}
#[cfg(test)]
mod tests {
    use std::sync::{Arc, mpsc};
    use std::time::Duration;

    use super::*;
    use crate::capture::CameraEvent;

    #[test]
    fn a_missing_camera_reports_one_error() {
        let config = CameraConfig {
            device_index: 99,
            ..CameraConfig::default()
        };
        assert_eq!(
            open_camera(&config).err(),
            Some("Could not open camera 99".to_owned())
        );
        let (tx, rx) = mpsc::channel();
        let mut capture = CameraCapture::start(
            config,
            Arc::new(|| 0.0),
            Box::new(move |event| {
                let _ = tx.send(event);
            }),
        );
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(30)),
            Ok(CameraEvent::Error("Could not open camera 99".to_owned()))
        );
        capture.stop();
        assert!(rx.try_recv().is_err());
    }
}
