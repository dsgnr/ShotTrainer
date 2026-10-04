//! Microphone capture over cpal.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Sender};
use std::sync::{Arc, Mutex, MutexGuard, PoisonError};
use std::thread::JoinHandle;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};

use crate::models::ShotDetectorSettings;
use crate::pipeline::{AudioEvent, AudioPipeline, ClockFn};

const DEFAULT_NAME: &str = "default";

/// Names of every input device, led by `"default"`. Position `n` is the device
/// that `DeviceSelector::Index(n)` opens. Falls back to `["default"]` when the
/// host cannot enumerate devices.
pub fn list_audio_inputs() -> Vec<String> {
    let mut names = vec![DEFAULT_NAME.to_owned()];
    match input_devices(&cpal::default_host()) {
        Ok(devices) => names.extend(devices.into_iter().map(|(name, _)| name)),
        Err(error) => log::warn!("Could not enumerate audio devices: {error}"),
    }
    names
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DeviceSelector {
    Default,
    Index(usize),
    Name(String),
}

impl DeviceSelector {
    /// `None`, `""` and `"default"` (any case) select the default device, an
    /// all-ASCII-digit string is an index into `list_audio_inputs`, and
    /// anything else is a case-insensitive substring of a device name.
    pub fn parse(text: Option<&str>) -> Self {
        let text = text.map_or("", str::trim);
        if text.is_empty() || text.eq_ignore_ascii_case(DEFAULT_NAME) {
            return DeviceSelector::Default;
        }
        if text.bytes().all(|b| b.is_ascii_digit())
            && let Ok(index) = text.parse()
        {
            return DeviceSelector::Index(index);
        }
        DeviceSelector::Name(text.to_owned())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SampleFormat {
    F32,
    I16,
    U16,
}

impl SampleFormat {
    fn preference(self) -> u8 {
        match self {
            SampleFormat::F32 => 0,
            SampleFormat::I16 => 1,
            SampleFormat::U16 => 2,
        }
    }

    fn from_cpal(format: cpal::SampleFormat) -> Option<Self> {
        match format {
            cpal::SampleFormat::F32 => Some(SampleFormat::F32),
            cpal::SampleFormat::I16 => Some(SampleFormat::I16),
            cpal::SampleFormat::U16 => Some(SampleFormat::U16),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SupportedRange {
    pub channels: u16,
    pub min_rate: u32,
    pub max_rate: u32,
    pub format: SampleFormat,
}

impl SupportedRange {
    fn contains(&self, rate: u32) -> bool {
        self.channels > 0 && (self.min_rate..=self.max_rate).contains(&rate)
    }
}

/// What the stream is opened with.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StreamChoice {
    pub sample_rate: u32,
    pub channels: u16,
    pub sample_format: SampleFormat,
}

/// Prefers `wanted_rate` with one channel, then `wanted_rate` with the fewest
/// channels, then the range containing `default_rate`. Within a stage the
/// order is fewest channels, then F32, I16, U16. `None` when no range
/// qualifies.
pub fn choose_config(
    ranges: &[SupportedRange],
    wanted_rate: u32,
    default_rate: Option<u32>,
) -> Option<StreamChoice> {
    let best_at = |rate: u32, mono_only: bool| {
        ranges
            .iter()
            .filter(|r| r.contains(rate) && (!mono_only || r.channels == 1))
            .min_by_key(|r| (r.channels, r.format.preference()))
            .map(|r| StreamChoice {
                sample_rate: rate,
                channels: r.channels,
                sample_format: r.format,
            })
    };
    best_at(wanted_rate, true)
        .or_else(|| best_at(wanted_rate, false))
        .or_else(|| default_rate.and_then(|rate| best_at(rate, false)))
}

/// A cpal sample type that converts to `f32` in `-1.0..=1.0`.
pub trait InputSample: cpal::SizedSample + Copy {
    fn to_f32(self) -> f32;
}

impl InputSample for f32 {
    fn to_f32(self) -> f32 {
        self
    }
}

impl InputSample for i16 {
    fn to_f32(self) -> f32 {
        f32::from(self) / 32768.0
    }
}

impl InputSample for u16 {
    fn to_f32(self) -> f32 {
        (f32::from(self) - 32768.0) / 32768.0
    }
}

pub fn to_f32<T: InputSample>(samples: &[T]) -> Vec<f32> {
    samples.iter().map(|s| s.to_f32()).collect()
}

#[derive(Debug, thiserror::Error)]
enum OpenError {
    #[error("{0}")]
    Cpal(#[from] cpal::Error),
    #[error("no input device matches {0}")]
    NoDevice(String),
    #[error("the device has no usable input configuration")]
    NoConfig,
}

type Devices = Vec<(String, cpal::Device)>;

fn input_devices(host: &cpal::Host) -> Result<Devices, cpal::Error> {
    Ok(host
        .input_devices()?
        .map(|device| {
            let name = device
                .description()
                .map(|d| d.name().to_owned())
                .unwrap_or_default();
            (name, device)
        })
        .collect())
}

fn select_device(host: &cpal::Host, selector: &DeviceSelector) -> Result<cpal::Device, OpenError> {
    let default = || {
        host.default_input_device()
            .ok_or_else(|| OpenError::NoDevice(DEFAULT_NAME.to_owned()))
    };
    match selector {
        DeviceSelector::Default | DeviceSelector::Index(0) => default(),
        DeviceSelector::Index(n) => input_devices(host)?
            .into_iter()
            .nth(n - 1)
            .map(|(_, device)| device)
            .ok_or_else(|| OpenError::NoDevice(format!("index {n}"))),
        DeviceSelector::Name(text) => {
            let needle = text.to_lowercase();
            input_devices(host)?
                .into_iter()
                .find(|(name, _)| name.to_lowercase().contains(&needle))
                .map(|(_, device)| device)
                .ok_or_else(|| OpenError::NoDevice(format!("\"{text}\"")))
        }
    }
}

struct Shared {
    settings: ShotDetectorSettings,
    pipeline: Option<AudioPipeline>,
}

type SharedState = Arc<Mutex<Shared>>;
type Sink = Arc<dyn Fn(AudioEvent) + Send + Sync + 'static>;

fn lock(shared: &SharedState) -> MutexGuard<'_, Shared> {
    shared.lock().unwrap_or_else(PoisonError::into_inner)
}

pub struct AudioInput {
    shared: SharedState,
    on_event: Sink,
    started: Arc<AtomicBool>,
    stop_tx: Option<Sender<()>>,
    thread: Option<JoinHandle<()>>,
}

/// A built stream that can be started. Dropping it releases the device.
trait InputStream {
    fn play(&self) -> Result<(), String>;
}

impl InputStream for cpal::Stream {
    fn play(&self) -> Result<(), String> {
        StreamTrait::play(self).map_err(|error| error.to_string())
    }
}

/// Builds a stream on the stream thread. The callback it installs must drop
/// buffers until the `live` flag is set.
type Opener = Box<
    dyn FnOnce(&SharedState, &Sink, &Arc<AtomicBool>) -> Result<Box<dyn InputStream>, String>
        + Send,
>;

impl AudioInput {
    /// Spawns the stream thread and returns at once, because opening can block
    /// while the operating system asks for microphone permission.
    ///
    /// Events arrive through `on_event` from the stream thread and the audio
    /// callback thread. A failed open or play yields one `Error` and nothing
    /// else. Otherwise `Started` is the first event, `Error` may follow any
    /// number of times while the stream runs, and `Stopped` is emitted exactly
    /// once by `stop()` or on drop. If the stream thread cannot be spawned the
    /// `Error` is delivered on the caller's thread before `start` returns, so
    /// `on_event` must not wait on state the caller holds.
    pub fn start(
        settings: ShotDetectorSettings,
        device: DeviceSelector,
        clock: ClockFn,
        on_event: Box<dyn Fn(AudioEvent) + Send + Sync + 'static>,
    ) -> AudioInput {
        let opener: Opener = Box::new(move |shared, sink, live| {
            open_stream(&device, shared, clock, sink, live)
                .map(|stream| Box::new(stream) as Box<dyn InputStream>)
                .map_err(|error| error.to_string())
        });
        Self::start_with(settings, on_event, opener)
    }

    fn start_with(
        settings: ShotDetectorSettings,
        on_event: Box<dyn Fn(AudioEvent) + Send + Sync + 'static>,
        opener: Opener,
    ) -> AudioInput {
        let shared = Arc::new(Mutex::new(Shared {
            settings,
            pipeline: None,
        }));
        let on_event: Sink = Arc::from(on_event);
        let started = Arc::new(AtomicBool::new(false));
        let live = Arc::new(AtomicBool::new(false));
        let (stop_tx, stop_rx) = mpsc::channel();

        let thread = {
            let (shared, on_event, started) = (shared.clone(), on_event.clone(), started.clone());
            std::thread::Builder::new()
                .name("audio-input".to_owned())
                .spawn(move || {
                    // The stream is created and dropped here because it is not
                    // `Send` on every host.
                    let stream = opener(&shared, &on_event, &live).and_then(|stream| {
                        stream.play()?;
                        Ok(stream)
                    });
                    match stream {
                        Ok(stream) => {
                            // The callback drops buffers until `live`, so no
                            // `Level` can precede `Started`.
                            started.store(true, Ordering::SeqCst);
                            on_event(AudioEvent::Started);
                            live.store(true, Ordering::SeqCst);
                            // Returns on a stop request or when the handle is dropped.
                            let _ = stop_rx.recv();
                            drop(stream);
                        }
                        Err(error) => {
                            on_event(AudioEvent::Error(format!(
                                "Could not open microphone: {error}"
                            )));
                        }
                    }
                })
        };
        let thread = match thread {
            Ok(handle) => Some(handle),
            Err(error) => {
                on_event(AudioEvent::Error(format!(
                    "Could not open microphone: {error}"
                )));
                None
            }
        };
        AudioInput {
            shared,
            on_event,
            started,
            stop_tx: Some(stop_tx),
            thread,
        }
    }

    /// Takes effect from the next block. A new `block_size` applies from the
    /// next block that is cut, whereas Python fixes the block size when the
    /// stream opens. The audio callback only holds the
    /// lock while it pushes one buffer, so this waits at most that long.
    pub fn update_settings(&self, settings: ShotDetectorSettings) {
        let mut shared = lock(&self.shared);
        if let Some(pipeline) = shared.pipeline.as_mut() {
            pipeline.update_settings(settings.clone());
        }
        shared.settings = settings;
    }

    /// Joins the stream thread and emits `Stopped` if the stream had started.
    /// Safe to call repeatedly. Blocks while a pending open is still waiting
    /// on the operating system.
    pub fn stop(&mut self) {
        if let Some(stop_tx) = self.stop_tx.take() {
            let _ = stop_tx.send(());
        }
        if let Some(thread) = self.thread.take() {
            if thread.join().is_err() {
                log::error!("audio input thread panicked");
            }
            if self.started.swap(false, Ordering::SeqCst) {
                (self.on_event)(AudioEvent::Stopped);
            }
        }
    }
}

impl Drop for AudioInput {
    fn drop(&mut self) {
        self.stop();
    }
}

fn open_stream(
    selector: &DeviceSelector,
    shared: &SharedState,
    clock: ClockFn,
    on_event: &Sink,
    live: &Arc<AtomicBool>,
) -> Result<cpal::Stream, OpenError> {
    let host = cpal::default_host();
    let device = select_device(&host, selector)?;

    let ranges: Vec<SupportedRange> = device
        .supported_input_configs()?
        .filter_map(|r| {
            Some(SupportedRange {
                channels: r.channels(),
                min_rate: r.min_sample_rate(),
                max_rate: r.max_sample_rate(),
                format: SampleFormat::from_cpal(r.sample_format())?,
            })
        })
        .collect();
    let default_rate = device.default_input_config().ok().map(|c| c.sample_rate());
    let wanted_rate = lock(shared).settings.sample_rate;
    let choice = choose_config(&ranges, wanted_rate, default_rate).ok_or(OpenError::NoConfig)?;

    {
        let mut guard = lock(shared);
        let pipeline = AudioPipeline::new(
            guard.settings.clone(),
            choice.sample_rate,
            choice.channels,
            clock,
        );
        guard.pipeline = Some(pipeline);
    }

    let config = cpal::StreamConfig {
        channels: choice.channels,
        sample_rate: choice.sample_rate,
        buffer_size: cpal::BufferSize::Default,
    };
    let stream = match choice.sample_format {
        SampleFormat::F32 => build::<f32>(&device, config, shared, on_event, live),
        SampleFormat::I16 => build::<i16>(&device, config, shared, on_event, live),
        SampleFormat::U16 => build::<u16>(&device, config, shared, on_event, live),
    }?;
    Ok(stream)
}

fn build<T: InputSample>(
    device: &cpal::Device,
    config: cpal::StreamConfig,
    shared: &SharedState,
    on_event: &Sink,
    live: &Arc<AtomicBool>,
) -> Result<cpal::Stream, cpal::Error> {
    let (data_shared, data_sink) = (shared.clone(), on_event.clone());
    let error_sink = on_event.clone();
    let (data_live, error_live) = (live.clone(), live.clone());
    let mut scratch: Vec<f32> = Vec::new();
    device.build_input_stream(
        config,
        move |data: &[T], _: &cpal::InputCallbackInfo| {
            if !data_live.load(Ordering::SeqCst) {
                return;
            }
            scratch.clear();
            scratch.extend(data.iter().map(|s| s.to_f32()));
            let events = match lock(&data_shared).pipeline.as_mut() {
                Some(pipeline) => pipeline.push(&scratch),
                None => Vec::new(),
            };
            for event in events {
                data_sink(event);
            }
        },
        move |error: cpal::Error| match error.kind() {
            cpal::ErrorKind::Xrun => log::debug!("audio status: {error}"),
            _ if error_live.load(Ordering::SeqCst) => {
                error_sink(AudioEvent::Error(format!("Audio stream error: {error}")))
            }
            _ => log::warn!("audio stream error before start: {error}"),
        },
        None,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;
    use std::time::Duration;

    fn range(channels: u16, min_rate: u32, max_rate: u32, format: SampleFormat) -> SupportedRange {
        SupportedRange {
            channels,
            min_rate,
            max_rate,
            format,
        }
    }

    fn choice(sample_rate: u32, channels: u16, sample_format: SampleFormat) -> StreamChoice {
        StreamChoice {
            sample_rate,
            channels,
            sample_format,
        }
    }

    #[test]
    fn parse_maps_default_spellings() {
        for text in [None, Some(""), Some("default"), Some("DEFAULT"), Some("  ")] {
            assert_eq!(
                DeviceSelector::parse(text),
                DeviceSelector::Default,
                "{text:?}"
            );
        }
    }

    #[test]
    fn parse_maps_ascii_digits_to_an_index() {
        assert_eq!(DeviceSelector::parse(Some("0")), DeviceSelector::Index(0));
        assert_eq!(DeviceSelector::parse(Some("12")), DeviceSelector::Index(12));
        assert_eq!(DeviceSelector::parse(Some(" 3 ")), DeviceSelector::Index(3));
    }

    #[test]
    fn parse_treats_anything_else_as_a_name() {
        assert_eq!(
            DeviceSelector::parse(Some("usb mic")),
            DeviceSelector::Name("usb mic".into())
        );
        assert_eq!(
            DeviceSelector::parse(Some("\u{663}")),
            DeviceSelector::Name("\u{663}".into())
        );
        let too_big = "99999999999999999999999999";
        assert_eq!(
            DeviceSelector::parse(Some(too_big)),
            DeviceSelector::Name(too_big.into())
        );
    }

    #[test]
    fn choose_config_prefers_the_exact_mono_f32_range() {
        let ranges = [
            range(2, 8000, 96000, SampleFormat::F32),
            range(1, 8000, 48000, SampleFormat::I16),
            range(1, 44100, 44100, SampleFormat::F32),
        ];
        assert_eq!(
            choose_config(&ranges, 44100, Some(48000)),
            Some(choice(44100, 1, SampleFormat::F32))
        );
    }

    #[test]
    fn choose_config_accepts_stereo_when_nothing_is_mono() {
        let ranges = [range(2, 48000, 48000, SampleFormat::I16)];
        assert_eq!(
            choose_config(&ranges, 48000, None),
            Some(choice(48000, 2, SampleFormat::I16))
        );
    }

    #[test]
    fn choose_config_clamps_a_wide_range_to_the_wanted_rate() {
        let ranges = [range(1, 8000, 96000, SampleFormat::F32)];
        assert_eq!(
            choose_config(&ranges, 44100, Some(48000)),
            Some(choice(44100, 1, SampleFormat::F32))
        );
    }

    #[test]
    fn choose_config_falls_back_to_the_default_rate() {
        let ranges = [
            range(1, 16000, 16000, SampleFormat::F32),
            range(2, 48000, 48000, SampleFormat::F32),
            range(1, 48000, 48000, SampleFormat::I16),
        ];
        assert_eq!(
            choose_config(&ranges, 44100, Some(48000)),
            Some(choice(48000, 1, SampleFormat::I16))
        );
    }

    #[test]
    fn choose_config_gives_none_when_nothing_matches() {
        assert_eq!(choose_config(&[], 44100, Some(48000)), None);
        let ranges = [range(1, 16000, 16000, SampleFormat::F32)];
        assert_eq!(choose_config(&ranges, 44100, None), None);
        assert_eq!(choose_config(&ranges, 44100, Some(48000)), None);
        assert_eq!(
            choose_config(&[range(0, 44100, 44100, SampleFormat::F32)], 44100, None),
            None
        );
    }

    #[test]
    fn choose_config_orders_formats_f32_i16_u16() {
        let mut ranges = vec![
            range(1, 44100, 44100, SampleFormat::U16),
            range(1, 44100, 44100, SampleFormat::I16),
            range(1, 44100, 44100, SampleFormat::F32),
        ];
        let formats =
            |ranges: &[SupportedRange]| choose_config(ranges, 44100, None).unwrap().sample_format;
        assert_eq!(formats(&ranges), SampleFormat::F32);
        ranges.remove(2);
        assert_eq!(formats(&ranges), SampleFormat::I16);
        ranges.remove(1);
        assert_eq!(formats(&ranges), SampleFormat::U16);
    }

    #[test]
    fn choose_config_prefers_mono_over_a_better_format_at_the_wanted_rate() {
        let ranges = [
            range(2, 44100, 44100, SampleFormat::F32),
            range(1, 44100, 44100, SampleFormat::U16),
        ];
        assert_eq!(
            choose_config(&ranges, 44100, None),
            Some(choice(44100, 1, SampleFormat::U16))
        );
    }

    #[test]
    fn to_f32_converts_the_extremes() {
        assert_eq!(to_f32(&[0.5_f32, -1.0]), vec![0.5, -1.0]);
        assert_eq!(
            to_f32(&[i16::MIN, 0, i16::MAX]),
            vec![-1.0, 0.0, 32767.0 / 32768.0]
        );
        assert!(to_f32(&[i16::MAX])[0] < 1.0);
        assert_eq!(
            to_f32(&[0_u16, 32768, u16::MAX]),
            vec![-1.0, 0.0, 32767.0 / 32768.0]
        );
    }

    fn collect_events(opener: Opener) -> (AudioInput, mpsc::Receiver<AudioEvent>) {
        let (tx, rx) = mpsc::channel();
        let tx = std::sync::Mutex::new(tx);
        let input = AudioInput::start_with(
            ShotDetectorSettings::default(),
            Box::new(move |event| {
                let _ = tx.lock().unwrap().send(event);
            }),
            opener,
        );
        (input, rx)
    }

    struct FakeStream {
        play_result: Result<(), String>,
    }

    impl InputStream for FakeStream {
        fn play(&self) -> Result<(), String> {
            self.play_result.clone()
        }
    }

    #[test]
    fn a_running_stream_emits_started_first_and_stopped_once() {
        let opener: Opener = Box::new(|_, _, live| {
            assert!(!live.load(Ordering::SeqCst));
            Ok(Box::new(FakeStream {
                play_result: Ok(()),
            }))
        });
        let (mut input, rx) = collect_events(opener);
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(5)).unwrap(),
            AudioEvent::Started
        );
        input.stop();
        input.stop();
        assert_eq!(rx.try_recv().unwrap(), AudioEvent::Stopped);
        drop(input);
        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn a_failed_play_emits_one_error_and_nothing_else() {
        let opener: Opener = Box::new(|_, _, _| {
            Ok(Box::new(FakeStream {
                play_result: Err("denied".to_owned()),
            }))
        });
        let (mut input, rx) = collect_events(opener);
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(5)).unwrap(),
            AudioEvent::Error("Could not open microphone: denied".to_owned())
        );
        input.stop();
        drop(input);
        assert!(rx.try_recv().is_err());
    }

    #[test]
    fn a_failed_build_emits_one_error_and_nothing_else() {
        let opener: Opener = Box::new(|_, _, _| Err("no device".to_owned()));
        let (mut input, rx) = collect_events(opener);
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(5)).unwrap(),
            AudioEvent::Error("Could not open microphone: no device".to_owned())
        );
        input.stop();
        assert!(rx.try_recv().is_err());
    }

    fn start_expecting_error(device: DeviceSelector) {
        let (tx, rx) = mpsc::channel();
        let tx = std::sync::Mutex::new(tx);
        let clock: ClockFn = std::sync::Arc::new(|| 0.0);
        let mut input = AudioInput::start(
            ShotDetectorSettings::default(),
            device,
            clock,
            Box::new(move |event| {
                let _ = tx.lock().unwrap().send(event);
            }),
        );
        let first = rx
            .recv_timeout(Duration::from_secs(20))
            .expect("no event arrived within 20 seconds");
        match first {
            AudioEvent::Error(message) => {
                assert!(
                    message.starts_with("Could not open microphone: "),
                    "{message}"
                );
            }
            other => panic!("expected an Error event, got {other:?}"),
        }
        input.stop();
        input.stop();
        assert!(
            rx.try_recv().is_err(),
            "a failed open must not emit Started or Stopped"
        );
    }

    #[test]
    fn unknown_device_name_reports_an_error_and_stops_cleanly() {
        start_expecting_error(DeviceSelector::Name("no such device zzz".into()));
    }

    #[test]
    fn out_of_range_index_reports_an_error() {
        start_expecting_error(DeviceSelector::Index(100_000));
    }
}
