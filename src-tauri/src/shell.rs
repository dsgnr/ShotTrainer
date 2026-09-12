//! The Tauri application, its commands and the [`Outlet`] that reaches the
//! webview.

use std::sync::{Arc, Mutex, PoisonError};

use shottrainer_controller::ControllerConfig;
use tauri::ipc::{Channel, InvokeResponseBody};
use tauri::{AppHandle, Emitter, Manager, RunEvent, Runtime, State, Wry};

use crate::bridge::{Bridge, Outlet, ShellConfig, ShellStatus};
use crate::logging;
use crate::mode::{self, DeviceMode, FAKE_DEVICES_ENV};
use crate::wire::{UI_EVENT, WireCommand, WireEvent};

pub struct TauriOutlet<R: Runtime> {
    app: AppHandle<R>,
    channel: Mutex<Option<Channel<InvokeResponseBody>>>,
}

impl<R: Runtime> TauriOutlet<R> {
    fn new(app: AppHandle<R>) -> Self {
        TauriOutlet {
            app,
            channel: Mutex::new(None),
        }
    }

    fn set_channel(&self, channel: Channel<InvokeResponseBody>) {
        *self.channel.lock().unwrap_or_else(PoisonError::into_inner) = Some(channel);
    }
}

impl<R: Runtime> Outlet for TauriOutlet<R> {
    fn emit(&self, event: &WireEvent) {
        if let Err(error) = self.app.emit(UI_EVENT, event) {
            log::warn!("Could not emit an event to the webview: {error}");
        }
    }

    fn send_pixels(&self, packet: Vec<u8>) -> bool {
        let channel = self
            .channel
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone();
        channel.is_some_and(|channel| channel.send(InvokeResponseBody::Raw(packet)).is_ok())
    }
}

type Shell = Bridge<TauriOutlet<Wry>>;

#[tauri::command]
fn send_command(shell: State<'_, Shell>, command: WireCommand) -> Result<(), String> {
    shell.send(command.into())
}

#[tauri::command]
fn frontend_ready(shell: State<'_, Shell>) -> Result<(), String> {
    log::info!("The webview is listening");
    shell.ready()
}

#[tauri::command]
fn subscribe_frames(shell: State<'_, Shell>, on_frame: Channel<InvokeResponseBody>) {
    shell.outlet().set_channel(on_frame);
    shell.frames_subscribed();
}

#[tauri::command]
fn frame_drawn(shell: State<'_, Shell>) {
    shell.frame_drawn();
}

#[tauri::command]
fn controller_status(shell: State<'_, Shell>) -> ShellStatus {
    shell.status()
}

#[tauri::command]
fn restart_controller(shell: State<'_, Shell>) -> Result<(), String> {
    shell.restart()
}

/// Starts the controller once device access is settled. On macOS the
/// system prompts for the camera and the microphone are requested here, on
/// the main thread, and the devices open after both are answered.
fn start_when_permitted(app: &AppHandle, mode: DeviceMode) {
    #[cfg(target_os = "macos")]
    if mode == DeviceMode::System {
        use crate::permissions::{Media, StartGate, macos};

        let gate = StartGate::new(2, {
            let app = app.clone();
            move || app.state::<Shell>().start()
        });
        for media in [Media::Camera, Media::Microphone] {
            let (gate, app) = (gate.clone(), app.clone());
            macos::request_access(media, move |granted| {
                if !granted {
                    app.state::<Shell>().access_denied(media.name());
                }
                gate.answered();
            });
        }
        return;
    }
    #[cfg(not(target_os = "macos"))]
    let _ = mode;
    app.state::<Shell>().start();
}

pub fn run() {
    logging::init();
    let mode = mode::device_mode(
        std::env::args().skip(1),
        std::env::var(FAKE_DEVICES_ENV).ok().as_deref(),
        cfg!(feature = "opencv"),
    );
    if mode == DeviceMode::Fake {
        log::info!("Using fake devices");
    }
    let app = tauri::Builder::default()
        .setup(move |app| {
            let config = ShellConfig {
                controller: ControllerConfig {
                    paths: mode::data_paths(mode),
                    app_version: env!("CARGO_PKG_VERSION").to_owned(),
                },
                backends: Arc::new(move || mode::backends(mode)),
                mode,
            };
            let shell = Bridge::new(TauriOutlet::new(app.handle().clone()), config);
            // A failure is reported to the webview through `controller_status`.
            let _ = shell.spawn();
            app.manage(shell);
            start_when_permitted(app.handle(), mode);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            send_command,
            frontend_ready,
            subscribe_frames,
            frame_drawn,
            controller_status,
            restart_controller,
        ])
        .build(tauri::generate_context!());
    match app {
        Ok(app) => app.run(|app, event| {
            if let RunEvent::Exit = event {
                app.state::<Shell>().shutdown();
            }
        }),
        Err(error) => {
            log::error!("Could not start ShotTrainer: {error}");
            std::process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;
    use std::time::Duration;

    use tauri::Listener;

    use super::*;

    #[test]
    fn events_reach_listeners_as_tagged_json() {
        let app = tauri::test::mock_app();
        let outlet = TauriOutlet::new(app.handle().clone());
        let (sender, receiver) = mpsc::channel();
        let sender = Mutex::new(sender);
        app.listen(UI_EVENT, move |event| {
            let _ = sender.lock().unwrap().send(event.payload().to_owned());
        });
        outlet.emit(&WireEvent::AudioLevel { level: 0.5 });
        let payload = receiver.recv_timeout(Duration::from_secs(5)).unwrap();
        assert_eq!(payload, r#"{"type":"audioLevel","level":0.5}"#);
    }

    #[test]
    fn pixels_go_to_the_subscribed_channel_as_raw_bytes() {
        let app = tauri::test::mock_app();
        let outlet = TauriOutlet::new(app.handle().clone());
        assert!(!outlet.send_pixels(vec![1, 2, 3]));
        let received = Arc::new(Mutex::new(Vec::new()));
        outlet.set_channel(Channel::new({
            let received = received.clone();
            move |body| {
                received.lock().unwrap().push(body);
                Ok(())
            }
        }));
        assert!(outlet.send_pixels(vec![1, 2, 3]));
        let received = received.lock().unwrap();
        assert!(
            matches!(received.as_slice(), [InvokeResponseBody::Raw(bytes)] if bytes == &[1, 2, 3])
        );
    }

    #[test]
    fn a_channel_that_fails_reports_the_pixels_undelivered() {
        let app = tauri::test::mock_app();
        let outlet = TauriOutlet::new(app.handle().clone());
        outlet.set_channel(Channel::new(|_| Err(tauri::Error::FailedToReceiveMessage)));
        assert!(!outlet.send_pixels(vec![1]));
    }
}
