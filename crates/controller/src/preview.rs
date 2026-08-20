//! Port of `app/preferences_manager.py`, covering the live preview while the
//! Preferences dialog is open, auto-optimise and the detector reset. Preview
//! changes update the cached preferences and the frame transform only, so
//! cancelling restores them and saving goes through `SetPreferences`.

use shottrainer_settings::Preferences;
use shottrainer_settings::stores::{clear_detector_settings, save_detector_settings};
use shottrainer_tracking::detector::{DetectorSettings, TargetDetector};
use shottrainer_tracking::frame::Frame;
use shottrainer_tracking::tuning::{HoughScorer, TuningGrid, optimise_detector_settings};

use crate::controller::{Controller, ImageControl};
use crate::convert::{detector_to_store, frame_transform};
use crate::events::{StatusMessage, UiEvent};

/// Lets the boxed scorer be passed where a sized scorer is expected.
struct DynScorer<'a>(&'a mut (dyn HoughScorer + Send));

impl HoughScorer for DynScorer<'_> {
    fn hough_score(&mut self, adjusted: &Frame, blur: i32, base: &DetectorSettings) -> Option<f64> {
        self.0.hough_score(adjusted, blur, base)
    }
}

impl Controller {
    /// Remembers the preferences to restore on cancel and shows the camera
    /// the dialog has selected.
    pub(crate) fn begin_preview(&mut self, camera_id: Option<i32>) {
        self.preview = Some(self.prefs.clone());
        if camera_id != self.camera.device_index() {
            self.preview_camera(camera_id);
        }
    }

    pub(crate) fn preview_camera(&mut self, camera_id: Option<i32>) {
        match camera_id {
            None => {
                self.stop_camera();
                self.emit(UiEvent::TrackingStatusText("No camera selected".to_owned()));
            }
            Some(index) => self.camera.start(index),
        }
    }

    /// A slider never sends a non-finite value, so one is ignored.
    pub(crate) fn preview_image(&mut self, control: ImageControl, value: f64) {
        if !value.is_finite() {
            log::warn!("Ignoring a non-finite {control:?} value");
            return;
        }
        let mut prefs = self.prefs.clone();
        match control {
            ImageControl::Brightness => prefs.camera_brightness = value,
            ImageControl::Contrast => prefs.camera_contrast = value,
        }
        self.set_preview_preferences(prefs);
    }

    /// Only the rotations the dialog offers are accepted, because any other
    /// would drop every frame.
    pub(crate) fn preview_transform(&mut self, rotation: i32, flip_h: bool, flip_v: bool) {
        if ![0, 90, 180, 270].contains(&rotation) {
            log::warn!("Ignoring an unsupported rotation of {rotation} degrees");
            return;
        }
        let prefs = Preferences {
            camera_rotation: rotation,
            camera_flip_h: flip_h,
            camera_flip_v: flip_v,
            ..self.prefs.clone()
        };
        self.set_preview_preferences(prefs);
    }

    /// Restores the camera and the image settings unless the dialog saved.
    pub(crate) fn end_preview(&mut self, saved: bool) {
        let Some(original) = self.preview.take() else {
            return;
        };
        if saved {
            return;
        }
        if self.camera.device_index() != original.camera_id {
            match original.camera_id {
                None => self.stop_camera(),
                Some(index) => self.camera.start(index),
            }
        }
        self.set_preview_preferences(original);
    }

    /// Searches the latest frame for detector settings and an image
    /// adjustment. Runs inline as Python does, for about 100 ms.
    pub(crate) fn optimise(&mut self) {
        let Some(source) = self.frames.latest_unadjusted().cloned() else {
            self.detector_status(StatusMessage::warning(
                "No camera frame available to optimise from",
                4000,
            ));
            return;
        };
        self.emit_to_dialog(UiEvent::OptimiseEnabled(false));
        self.detector_status(StatusMessage::info("Optimising tracking...", 3000));
        let base = self.frames.tracker().detector().settings().clone();
        let result = optimise_detector_settings(
            &source,
            &base,
            &TuningGrid::default(),
            &mut DynScorer(&mut *self.scorer),
        );
        self.emit_to_dialog(UiEvent::OptimiseEnabled(true));
        let Some(settings) = result.settings else {
            self.detector_status(StatusMessage::warning(
                "Could not find a stable target in the current frame",
                4000,
            ));
            return;
        };
        let adjustment = result.adjustment;
        let unchanged = settings == base
            && adjustment.brightness == self.prefs.camera_brightness
            && adjustment.contrast == self.prefs.camera_contrast;
        self.frames
            .tracker_mut()
            .detector_mut()
            .set_settings(settings.clone());
        if let Err(error) =
            save_detector_settings(&detector_to_store(&settings), &self.paths.detector_settings)
        {
            log::warn!("Could not save detector settings: {error}");
        }
        let prefs = Preferences {
            camera_brightness: adjustment.brightness,
            camera_contrast: adjustment.contrast,
            ..self.prefs.clone()
        };
        self.set_preview_preferences(prefs);
        self.emit_to_dialog(UiEvent::ImageControls {
            brightness: adjustment.brightness,
            contrast: adjustment.contrast,
        });
        let score = result.score;
        self.detector_status(if unchanged {
            StatusMessage::info(format!("Already optimal (confidence {score:.2})"), 3000)
        } else {
            StatusMessage::success(format!("Tracking optimised (confidence {score:.2})"), 4000)
        });
    }

    /// Default detector settings with the preferred region, and no saved file.
    pub(crate) fn reset_detector(&mut self) {
        let defaults = DetectorSettings {
            region_fraction: self.prefs.tracking_region_fraction,
            ..DetectorSettings::default()
        };
        self.frames
            .tracker_mut()
            .detector_mut()
            .set_settings(defaults);
        if let Err(error) = clear_detector_settings(&self.paths.detector_settings) {
            log::warn!("Could not remove the detector settings: {error}");
        }
        self.detector_status(StatusMessage::info("Detector reset to defaults", 3000));
    }

    fn set_preview_preferences(&mut self, prefs: Preferences) {
        self.frames.set_transform(frame_transform(&prefs));
        self.prefs = prefs;
    }

    /// The status bar always, and the dialog when it is open.
    fn detector_status(&self, message: StatusMessage) {
        self.emit_to_dialog(UiEvent::DetectorStatus(message.clone()));
        self.message(message);
    }

    fn emit_to_dialog(&self, event: UiEvent) {
        if self.preview.is_some() {
            self.emit(event);
        }
    }
}

#[cfg(test)]
mod tests {
    use shottrainer_settings::stores::load_detector_settings;
    use shottrainer_tracking::capture::CameraEvent;
    use shottrainer_tracking::frame::PixelFormat;

    use super::*;
    use crate::controller::{Command, Input};
    use crate::convert::detector_from_store;
    use crate::fakes::TestRig;

    fn command(controller: &mut Controller, command: Command) {
        controller.handle(Input::Command(command));
    }

    fn brightness(controller: &mut Controller, value: f64) {
        command(
            controller,
            Command::PreviewImage {
                control: ImageControl::Brightness,
                value,
            },
        );
    }

    /// Runs one frame through the pipeline so the optimiser has a source.
    fn feed_frame(rig: &TestRig, controller: &mut Controller) {
        rig.camera.emit(
            0,
            CameraEvent::Frame {
                frame: Frame::filled(64, 48, PixelFormat::Grey, 90).unwrap(),
                timestamp: 0.0,
                frame_id: 1,
            },
        );
        rig.pump(controller);
    }

    #[test]
    fn image_previews_change_the_transform_but_are_not_saved() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        command(
            &mut controller,
            Command::BeginPreview { camera_id: Some(0) },
        );
        brightness(&mut controller, 50.0);
        command(
            &mut controller,
            Command::PreviewImage {
                control: ImageControl::Contrast,
                value: 1.5,
            },
        );
        assert_eq!(
            (
                controller.preferences().camera_brightness,
                controller.preferences().camera_contrast
            ),
            (50.0, 1.5)
        );
        assert_eq!(controller.frames().transform().brightness, 50.0);
        assert!(!rig.paths.settings.exists());
    }

    #[test]
    fn non_finite_values_and_odd_rotations_are_ignored() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        brightness(&mut controller, f64::NAN);
        command(
            &mut controller,
            Command::PreviewTransform {
                rotation_degrees: 45,
                flip_horizontal: true,
                flip_vertical: false,
            },
        );
        assert_eq!(controller.preferences(), &Preferences::default());
        command(
            &mut controller,
            Command::PreviewTransform {
                rotation_degrees: 90,
                flip_horizontal: true,
                flip_vertical: false,
            },
        );
        let transform = controller.frames().transform();
        assert_eq!(
            (transform.rotation_degrees, transform.flip_horizontal),
            (90, true)
        );
    }

    #[test]
    fn cancelling_restores_the_image_settings_and_saving_keeps_them() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        command(&mut controller, Command::BeginPreview { camera_id: None });
        brightness(&mut controller, 80.0);
        command(&mut controller, Command::EndPreview { saved: false });
        assert_eq!(controller.preferences().camera_brightness, 0.0);
        assert_eq!(controller.frames().transform().brightness, 0.0);

        command(&mut controller, Command::BeginPreview { camera_id: None });
        brightness(&mut controller, 80.0);
        command(&mut controller, Command::EndPreview { saved: true });
        assert_eq!(controller.preferences().camera_brightness, 80.0);
    }

    #[test]
    fn the_dialog_camera_is_previewed_and_restored_on_cancel() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        command(
            &mut controller,
            Command::BeginPreview { camera_id: Some(0) },
        );
        assert_eq!(rig.camera.state().started, [0], "already showing camera 0");
        command(&mut controller, Command::PreviewCamera(Some(2)));
        command(&mut controller, Command::EndPreview { saved: false });
        assert_eq!(rig.camera.state().started, [0, 2, 0]);
    }

    #[test]
    fn a_saved_dialog_keeps_the_new_camera() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        command(
            &mut controller,
            Command::BeginPreview { camera_id: Some(2) },
        );
        command(&mut controller, Command::EndPreview { saved: true });
        assert_eq!(rig.camera.state().started, [0, 2]);
    }

    #[test]
    fn choosing_no_camera_stops_it_and_says_so() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        rig.take();
        command(&mut controller, Command::PreviewCamera(None));
        let events = rig.take();
        assert_eq!(
            events,
            [
                UiEvent::CameraIdle,
                UiEvent::TrackingStatusText("No camera selected".into())
            ]
        );
    }

    #[test]
    fn optimise_without_a_frame_warns() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        rig.take();
        command(&mut controller, Command::Optimise);
        assert_eq!(
            rig.messages(),
            ["No camera frame available to optimise from"]
        );
    }

    #[test]
    fn optimise_applies_and_saves_the_best_settings() {
        let rig = TestRig::new();
        *rig.scorer.0.lock().unwrap() = Some(0.8);
        let mut controller = rig.build();
        controller.start();
        feed_frame(&rig, &mut controller);
        command(
            &mut controller,
            Command::BeginPreview { camera_id: Some(0) },
        );
        rig.take();
        command(&mut controller, Command::Optimise);
        let settings = controller.frames().tracker().detector().settings().clone();
        assert_eq!(
            (settings.blur_kernel, settings.adaptive_block_size),
            (3, 15)
        );
        let saved = load_detector_settings(&rig.paths.detector_settings).unwrap();
        assert_eq!(detector_from_store(&saved), settings);
        let prefs = controller.preferences();
        assert_eq!(
            (prefs.camera_brightness, prefs.camera_contrast),
            (-100.0, 0.5)
        );
        let events = rig.take();
        assert_eq!(events[0], UiEvent::OptimiseEnabled(false));
        assert!(events.contains(&UiEvent::ImageControls {
            brightness: -100.0,
            contrast: 0.5
        }));
        assert_eq!(
            events.last(),
            Some(&UiEvent::Message(StatusMessage::success(
                "Tracking optimised (confidence 0.80)",
                4000
            )))
        );
        command(&mut controller, Command::Optimise);
        assert_eq!(
            rig.messages().last().map(String::as_str),
            Some("Already optimal (confidence 0.80)")
        );
    }

    #[test]
    fn optimise_without_a_target_keeps_everything() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        feed_frame(&rig, &mut controller);
        rig.take();
        command(&mut controller, Command::Optimise);
        assert_eq!(
            rig.messages(),
            [
                "Optimising tracking...",
                "Could not find a stable target in the current frame"
            ]
        );
        assert!(!rig.paths.detector_settings.exists());
        assert_eq!(
            controller.frames().tracker().detector().settings(),
            &DetectorSettings::default()
        );
    }

    #[test]
    fn reset_restores_defaults_and_removes_the_file() {
        let rig = TestRig::new();
        save_detector_settings(
            &detector_to_store(&DetectorSettings {
                blur_kernel: 9,
                ..DetectorSettings::default()
            }),
            &rig.paths.detector_settings,
        )
        .unwrap();
        let mut controller = rig.build();
        command(
            &mut controller,
            Command::SetPreferences(Preferences {
                tracking_region_fraction: 0.4,
                ..Preferences::default()
            }),
        );
        rig.take();
        command(&mut controller, Command::ResetDetector);
        assert!(!rig.paths.detector_settings.exists());
        assert_eq!(
            controller.frames().tracker().detector().settings(),
            &DetectorSettings {
                region_fraction: 0.4,
                ..DetectorSettings::default()
            }
        );
        assert_eq!(rig.messages(), ["Detector reset to defaults"]);
    }

    #[test]
    fn transform_previews_carry_the_rotation_and_both_flips() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        command(
            &mut controller,
            Command::PreviewTransform {
                rotation_degrees: 270,
                flip_horizontal: false,
                flip_vertical: true,
            },
        );
        let transform = controller.frames().transform();
        assert_eq!(
            (
                transform.rotation_degrees,
                transform.flip_horizontal,
                transform.flip_vertical
            ),
            (270, false, true)
        );
        let prefs = controller.preferences();
        assert_eq!(
            (
                prefs.camera_rotation,
                prefs.camera_flip_h,
                prefs.camera_flip_v
            ),
            (270, false, true)
        );
    }

    #[test]
    fn cancelling_restores_the_preferences_from_when_the_dialog_opened() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        command(
            &mut controller,
            Command::SetPreferences(Preferences {
                camera_brightness: 20.0,
                ..Preferences::default()
            }),
        );
        command(&mut controller, Command::BeginPreview { camera_id: None });
        brightness(&mut controller, 80.0);
        command(&mut controller, Command::EndPreview { saved: false });
        assert_eq!(controller.preferences().camera_brightness, 20.0);
        assert_eq!(controller.frames().transform().brightness, 20.0);
    }

    #[test]
    fn cancelling_keeps_a_camera_that_never_changed() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        command(
            &mut controller,
            Command::BeginPreview { camera_id: Some(0) },
        );
        command(&mut controller, Command::EndPreview { saved: false });
        assert_eq!(rig.camera.state().started, [0]);
        assert_eq!(rig.camera.state().stopped, 0);
    }

    #[test]
    fn cancelling_stops_a_camera_the_dialog_started_when_none_was_in_use() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        command(
            &mut controller,
            Command::SetPreferences(Preferences {
                camera_id: None,
                ..Preferences::default()
            }),
        );
        command(
            &mut controller,
            Command::BeginPreview { camera_id: Some(1) },
        );
        assert_eq!(rig.camera.state().started, [1]);
        rig.take();
        command(&mut controller, Command::EndPreview { saved: false });
        assert_eq!(rig.camera.state().stopped, 1);
        assert_eq!(rig.take(), [UiEvent::CameraIdle]);
    }

    #[test]
    fn ending_a_preview_that_never_began_changes_nothing() {
        let rig = TestRig::new();
        let mut controller = rig.build();
        controller.start();
        command(&mut controller, Command::PreviewCamera(Some(2)));
        command(&mut controller, Command::EndPreview { saved: false });
        assert_eq!(rig.camera.state().started, [0, 2]);
    }

    #[test]
    fn optimise_reports_to_the_open_dialog_and_the_status_bar() {
        let rig = TestRig::new();
        *rig.scorer.0.lock().unwrap() = Some(0.8);
        let mut controller = rig.build();
        controller.start();
        feed_frame(&rig, &mut controller);
        command(
            &mut controller,
            Command::BeginPreview { camera_id: Some(0) },
        );
        rig.take();
        command(&mut controller, Command::Optimise);
        let optimising = StatusMessage::info("Optimising tracking...", 3000);
        let done = StatusMessage::success("Tracking optimised (confidence 0.80)", 4000);
        assert_eq!(
            rig.take(),
            [
                UiEvent::OptimiseEnabled(false),
                UiEvent::DetectorStatus(optimising.clone()),
                UiEvent::Message(optimising),
                UiEvent::OptimiseEnabled(true),
                UiEvent::ImageControls {
                    brightness: -100.0,
                    contrast: 0.5
                },
                UiEvent::DetectorStatus(done.clone()),
                UiEvent::Message(done),
            ]
        );
    }

    #[test]
    fn dialog_events_are_not_sent_while_no_dialog_is_open() {
        let rig = TestRig::new();
        *rig.scorer.0.lock().unwrap() = Some(0.8);
        let mut controller = rig.build();
        controller.start();
        feed_frame(&rig, &mut controller);
        rig.take();
        command(&mut controller, Command::Optimise);
        assert_eq!(
            rig.take(),
            [
                UiEvent::Message(StatusMessage::info("Optimising tracking...", 3000)),
                UiEvent::Message(StatusMessage::success(
                    "Tracking optimised (confidence 0.80)",
                    4000
                )),
            ]
        );
        command(&mut controller, Command::ResetDetector);
        assert_eq!(
            rig.take(),
            [UiEvent::Message(StatusMessage::info(
                "Detector reset to defaults",
                3000
            ))]
        );
    }

    #[test]
    fn optimise_is_only_optimal_when_settings_and_image_adjustment_both_match() {
        let rig = TestRig::new();
        *rig.scorer.0.lock().unwrap() = Some(0.8);
        let mut controller = rig.build();
        controller.start();
        feed_frame(&rig, &mut controller);
        let last = |rig: &TestRig| rig.messages().last().cloned().unwrap();

        // The image controls already match but the detector settings do not.
        brightness(&mut controller, -100.0);
        command(
            &mut controller,
            Command::PreviewImage {
                control: ImageControl::Contrast,
                value: 0.5,
            },
        );
        command(&mut controller, Command::Optimise);
        assert_eq!(last(&rig), "Tracking optimised (confidence 0.80)");

        // The detector settings match and only the brightness differs.
        brightness(&mut controller, 0.0);
        command(&mut controller, Command::Optimise);
        assert_eq!(last(&rig), "Tracking optimised (confidence 0.80)");

        // The detector settings match and only the contrast differs.
        command(
            &mut controller,
            Command::PreviewImage {
                control: ImageControl::Contrast,
                value: 1.0,
            },
        );
        command(&mut controller, Command::Optimise);
        assert_eq!(last(&rig), "Tracking optimised (confidence 0.80)");

        command(&mut controller, Command::Optimise);
        assert_eq!(last(&rig), "Already optimal (confidence 0.80)");
    }
}
