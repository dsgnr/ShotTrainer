//! Opens a microphone and prints levels and shots.
//!
//! Usage: `audio_input [DEVICE] [SECONDS]`. DEVICE is "default", an index from
//! the device list or part of a device name. SECONDS defaults to 5.

use std::process::ExitCode;
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use shottrainer_audio::models::ShotDetectorSettings;
use shottrainer_audio::{AudioEvent, AudioInput, ClockFn, DeviceSelector, list_audio_inputs};

const PRINT_INTERVAL: Duration = Duration::from_millis(100);

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() > 2 {
        eprintln!("usage: audio_input [DEVICE] [SECONDS]");
        return ExitCode::from(2);
    }
    let seconds = match args.get(1).map(|s| s.parse::<f64>()) {
        None => 5.0,
        Some(Ok(value)) if value.is_finite() && value > 0.0 => value,
        Some(_) => {
            eprintln!("SECONDS must be a positive number");
            return ExitCode::from(2);
        }
    };
    let selector = DeviceSelector::parse(args.first().map(String::as_str));

    println!("inputs: {:?}", list_audio_inputs());
    let origin = Instant::now();
    let clock: ClockFn = Arc::new(move || origin.elapsed().as_secs_f64());
    let (tx, rx) = mpsc::channel();
    let tx = Mutex::new(tx);
    let mut input = AudioInput::start(
        ShotDetectorSettings::default(),
        selector,
        clock,
        Box::new(move |event| {
            if let Ok(tx) = tx.lock() {
                let _ = tx.send(event);
            }
        }),
    );

    let deadline = origin + Duration::from_secs_f64(seconds);
    let mut window_start = Instant::now();
    let (mut peak, mut blocks) = (0.0_f64, 0_u32);
    let mut failed = false;
    while let Some(wait) = deadline.checked_duration_since(Instant::now()) {
        let Ok(event) = rx.recv_timeout(wait.min(PRINT_INTERVAL)) else {
            if window_start.elapsed() >= PRINT_INTERVAL {
                flush(&mut peak, &mut blocks, &mut window_start);
            }
            continue;
        };
        match event {
            AudioEvent::Level(level) => {
                peak = peak.max(level);
                blocks += 1;
                if window_start.elapsed() >= PRINT_INTERVAL {
                    flush(&mut peak, &mut blocks, &mut window_start);
                }
            }
            AudioEvent::Shot(shot) => println!(
                "shot at {:.3}s level {:.3} rate {}",
                shot.timestamp, shot.audio_level, shot.sample_rate
            ),
            AudioEvent::Error(message) => {
                println!("error: {message}");
                failed = true;
                break;
            }
            AudioEvent::Started => println!("started"),
            AudioEvent::Stopped => println!("stopped"),
        }
    }
    input.stop();
    while let Ok(event) = rx.try_recv() {
        if let AudioEvent::Stopped = event {
            println!("stopped");
        }
    }
    if failed {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}

fn flush(peak: &mut f64, blocks: &mut u32, window_start: &mut Instant) {
    if *blocks > 0 {
        println!("level peak {:.4} over {} blocks", peak, blocks);
    }
    *peak = 0.0;
    *blocks = 0;
    *window_start = Instant::now();
}
