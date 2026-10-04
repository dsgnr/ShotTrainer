//! Opens a camera through OpenCV, runs the circle detector on each frame and
//! prints a line about once a second. Needs a camera and camera permission.
//!
//! Usage: camera_capture [device_index] [seconds]

use std::sync::{Arc, mpsc};
use std::time::{Duration, Instant};

use shottrainer_tracking::capture::{CameraCapture, CameraConfig, CameraEvent, ClockFn};
use shottrainer_tracking::cv::CircleTargetDetector;
use shottrainer_tracking::detector::{DetectorSettings, TargetDetector};
use shottrainer_tracking::frame_ops::bgr_to_grey;

fn main() {
    let mut args = std::env::args().skip(1);
    let device_index = match args.next().map(|a| a.parse::<i32>()) {
        None => 0,
        Some(Ok(index)) => index,
        Some(Err(_)) => usage(),
    };
    let seconds = match args.next().map(|a| a.parse::<u64>()) {
        None => 5,
        Some(Ok(seconds)) => seconds,
        Some(Err(_)) => usage(),
    };

    let origin = Instant::now();
    let clock: ClockFn = Arc::new(move || origin.elapsed().as_secs_f64());
    let (tx, rx) = mpsc::channel();
    let config = CameraConfig {
        device_index,
        width: Some(640),
        height: Some(480),
        fps: Some(30.0),
        ..CameraConfig::default()
    };
    let mut capture = CameraCapture::start(
        config,
        clock,
        Box::new(move |event| {
            let _ = tx.send(event);
        }),
    );

    let mut detector = CircleTargetDetector::new(DetectorSettings::default());
    let deadline = Instant::now() + Duration::from_secs(seconds);
    let mut opened = false;
    let (mut frames, mut found) = (0_u64, 0_u64);
    let (mut first_ts, mut last_ts, mut max_gap) = (None, None, 0.0_f64);
    while let Some(remaining) = deadline.checked_duration_since(Instant::now()) {
        match rx.recv_timeout(remaining) {
            Ok(CameraEvent::Opened { width, height, fps }) => {
                opened = true;
                println!("opened {width}x{height}, driver reports {fps} fps");
            }
            Ok(CameraEvent::Frame {
                frame,
                timestamp,
                frame_id,
            }) => {
                frames += 1;
                first_ts.get_or_insert(timestamp);
                if let Some(previous) = last_ts {
                    max_gap = max_gap.max(timestamp - previous);
                }
                last_ts = Some(timestamp);
                let detection = detector.detect(&bgr_to_grey(frame));
                found += u64::from(detection.found);
                if frame_id % 30 == 0 {
                    println!(
                        "frame {frame_id} at {timestamp:.3} s: found={} x={:.1} y={:.1} r={:.1}",
                        detection.found, detection.x_px, detection.y_px, detection.radius_px
                    );
                }
            }
            Ok(CameraEvent::Error(message)) => {
                println!("error: {message}");
                if !opened {
                    break;
                }
            }
            Ok(CameraEvent::Closed) | Err(_) => break,
        }
    }
    capture.stop();
    let span = match (first_ts, last_ts) {
        (Some(first), Some(last)) if last > first => last - first,
        _ => 0.0,
    };
    let fps = if span > 0.0 {
        (frames - 1) as f64 / span
    } else {
        0.0
    };
    println!(
        "frames={frames} found={found} measured_fps={fps:.1} max_gap_ms={:.1}",
        max_gap * 1000.0
    );
}

fn usage() -> ! {
    eprintln!("usage: camera_capture [device_index] [seconds]");
    std::process::exit(2);
}
