"""Coordinates camera capture, tracking, audio, storage and the UI."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QObject

from shottrainer import __version__
from shottrainer.audio.input import AudioShotListener, list_audio_inputs
from shottrainer.audio.models import ShotDetectorSettings, ShotEvent
from shottrainer.replay.player import TracePlayer
from shottrainer.services.replay_coordinator import ReplayCoordinator
from shottrainer.services.scoring import ScoringRing, score_shot
from shottrainer.services.session_recorder import SessionRecorder
from shottrainer.services.shot_coordinator import (
    ShotCoordinator,
    ShotCoordinatorSettings,
)
from shottrainer.services.shot_stats import compute_trace_stats
from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.camera import CameraCapture, CameraConfig, list_available_cameras
from shottrainer.tracking.detector import DetectorSettings
from shottrainer.tracking.detector_tuning import optimise_detector_settings
from shottrainer.tracking.tracker import Tracker
from shottrainer.ui.main_window import MainWindow
from shottrainer.ui.preferences_dialog import Preferences
from shottrainer.ui.session_browser import SessionBrowserDialog
from shottrainer.ui.shot_list import ShotListEntry
from shottrainer.ui.target_faces import face_for_name, list_target_faces, rings_for_face
from shottrainer.ui.target_view import ShotMarker

from .camera_selection import (
    CameraSelection,
    load_camera_selection,
    resolve_camera_index,
    save_camera_selection,
)
from .capture_pipeline import CapturePipeline, FrameTransformOptions
from .detector_store import (
    clear_detector_settings,
    load_detector_settings,
    save_detector_settings,
)
from .settings import load_preferences, save_preferences
from .settings_watcher import SettingsWatcher
from .zero_offset_store import load_zero_offset, save_zero_offset

log = logging.getLogger(__name__)


@dataclass(slots=True)
class _ShotEntry:
    """One shot in the current on-screen list."""

    timestamp: float
    x_mm: float
    y_mm: float
    score: str | None = None


class AppController(QObject):
    """Connects UI signals to the underlying services.

    Owns the camera capture thread, the audio listener, the
    tracker, and the recorder and replay coordinators. Reacts to
    widget signals from :class:`MainWindow` and pushes results
    back via the same widgets. The controller doesn't draw
    anything itself.
    """

    # The status banner refreshes at most every N frames so it
    # doesn't repaint at the camera's full frame rate.
    _STATUS_REFRESH_EVERY_N_FRAMES = 5

    def __init__(self, window: MainWindow, db_path: Path) -> None:
        super().__init__()
        self._window = window

        engine = make_engine(db_path)
        init_database(engine)
        self._repo = SessionRepository(engine)

        prefs = load_preferences()
        self._tracker = Tracker(circle_diameter_mm=prefs.circle_diameter_mm)
        self._buffer = TraceBuffer(capacity=12000)
        self._recorder = SessionRecorder(self._repo)
        self._coordinator = ShotCoordinator(self._buffer)
        self._replay = ReplayCoordinator(self._repo)

        self._camera: CameraCapture | None = None
        self._audio = AudioShotListener()

        self._pipeline = CapturePipeline(
            tracker=self._tracker,
            buffer=self._buffer,
            recorder=self._recorder,
            on_frame=self._on_pipeline_frame,
            on_detection=self._on_pipeline_detection,
            on_no_detection=self._on_pipeline_miss,
        )

        self._player = TracePlayer(self)
        self._current_view_session_id: int | None = None
        self._shots_in_view: list[_ShotEntry] = []
        self._frame_mirrors: list[Any] = []  # dialogs that want live frames
        self._latest_frame: np.ndarray | None = None
        # The camera list as it was last enumerated. Refreshed
        # lazily when the Preferences dialog opens. Consulted by
        # ``_persist_camera_selection`` so saving the user's
        # choice doesn't need to re-probe the device tree. Empty
        # until Preferences has opened at least once.
        self._cached_camera_options: list[tuple[int, str]] = []

        self._settings_watcher = SettingsWatcher(parent=self)
        self._settings_watcher.changed.connect(self._on_settings_file_changed)

        self._connect_signals()
        self._window.set_device_options_provider(self._device_options)
        self._window.set_saved_camera_name_provider(
            lambda: load_camera_selection().name
        )
        self._window.set_target_faces_provider(list_target_faces)
        self._window.set_rings_lookup(rings_for_face)
        self._window.set_face_lookup(face_for_name)
        self._window.set_recording_check(lambda: self._recorder.is_recording)
        self._apply_preferences(prefs, persist=False)

        saved_detector = load_detector_settings()
        if saved_detector is not None:
            self._tracker.detector.settings = saved_detector

        self._settings_watcher.start()

        # Restore any saved zero offset and surface it in the UI.
        saved_offset = load_zero_offset()
        if saved_offset != (0.0, 0.0):
            self._tracker.set_zero_offset(*saved_offset)
        self._window.set_zero_offset_state(saved_offset != (0.0, 0.0), saved_offset)

    def start(self) -> None:
        """Start live preview. The camera and microphone run for as long as the app is open."""
        index = self._effective_camera_index()
        if index is not None:
            self._start_camera(index)
        self._audio.start()

    def shutdown(self) -> None:
        """Tear down threads and watchers in a sensible order."""
        # Stop the recorder first so anything still in flight (an
        # in-progress shot batch, for example) gets flushed before
        # the audio listener stops emitting events.
        if self._recorder.is_recording:
            self._recorder.stop()
        self._settings_watcher.stop()
        self._stop_camera()
        self._audio.stop()

    def _connect_signals(self) -> None:
        sc = self._window.session_controls
        sc.start_requested.connect(self._on_start_requested)
        sc.stop_requested.connect(self._on_stop_requested)
        sc.clear_shots_requested.connect(self._on_clear_shots_requested)

        rc = self._window.replay_controls
        rc.play_clicked.connect(self._player.play)
        rc.pause_clicked.connect(self._player.pause)
        rc.reset_clicked.connect(self._player.stop)
        rc.scrubbed.connect(self._player.seek_fraction)

        self._player.index_changed.connect(self._window.target_view.set_playhead_index)
        self._player.progress.connect(rc.set_progress)

        self._window.shot_list.shot_selected.connect(self._on_shot_selected)

        self._audio.shot_detected.connect(self._on_shot_detected)
        self._audio.error.connect(self._on_audio_error)
        self._audio.level.connect(self._on_audio_level)

        self._window.session_browser_requested.connect(self._open_session_browser)
        self._window.preferences_changed.connect(self._apply_preferences)
        self._window.preferences_dialog_opened.connect(self._on_prefs_dialog_opened)
        self._window.circle_diameter_changed.connect(self._on_circle_diameter_changed)
        self._window.zero_on_aim_requested.connect(self._on_zero_on_aim_requested)
        self._window.zero_cleared.connect(self._on_zero_cleared)
        self._window.rescore_requested.connect(self._on_rescore_requested)

    def _effective_camera_index(self) -> int | None:
        """Pick the camera index to use given the saved selection.

        Lists the attached devices (cheap via Qt's media stack)
        and prefers a match by name, so the saved camera follows
        the user across reboots even when USB devices renumber.
        Falls back to the saved index, then to ``0``. Returns
        ``None`` only when the user has explicitly chosen "no
        camera" and nothing is attached.
        """
        selection = load_camera_selection()
        if selection.index is None and not selection.name:
            # Explicit "no camera" choice. Honour it.
            return None
        try:
            available = list_available_cameras()
        except Exception:  # pragma: no cover - driver dependent
            available = []
        if not available:
            return selection.index if selection.index is not None else None
        return resolve_camera_index(selection, available)

    def _persist_camera_selection(self, index: int | None) -> None:
        """Save the camera the user just picked.

        Uses the cached enumeration from the most recent
        Preferences dialog (which is where the change comes from)
        so this path doesn't have to probe the device tree
        again. Falls back to a plain ``Camera N`` label when no
        cache is available. ``None`` saves as "no camera" so the
        next launch doesn't try to open whatever device landed
        at index 0.
        """
        if index is None:
            try:
                save_camera_selection(CameraSelection(name="", index=None))
            except OSError as exc:
                log.warning("Could not save camera selection: %s", exc)
            return
        name = next(
            (n for i, n in self._cached_camera_options if i == index),
            f"Camera {index}",
        )
        try:
            save_camera_selection(CameraSelection(name=name, index=index))
        except OSError as exc:
            log.warning("Could not save camera selection: %s", exc)

    def _start_camera(self, device_index: int) -> None:
        self._stop_camera()
        cam = CameraCapture(self._camera_config_from_prefs(device_index))
        cam.frame_ready.connect(self._on_frame)
        cam.error.connect(self._on_camera_error)
        cam.start()
        self._camera = cam

    def _camera_config_from_prefs(self, device_index: int) -> CameraConfig:
        prefs = getattr(self, "_preferences", None)
        if prefs is None:
            return CameraConfig(device_index=device_index)
        return CameraConfig(
            device_index=device_index,
            brightness=prefs.camera_brightness,
            contrast=prefs.camera_contrast,
            saturation=prefs.camera_saturation,
            gain=prefs.camera_gain,
            exposure=prefs.camera_exposure,
        )

    def _stop_camera(self) -> None:
        if self._camera is not None:
            self._camera.stop()
            self._camera = None
            self._window.camera_view.set_status("idle")

    def _device_options(self) -> tuple[list[tuple[int, str]], list[str]]:
        cameras = list_available_cameras() or [(0, "Camera 0")]
        mics = list_audio_inputs()
        # Cache so ``_persist_camera_selection`` doesn't re-probe.
        self._cached_camera_options = cameras
        return cameras, mics

    def _on_frame(self, frame: np.ndarray, ts: float, frame_id: int) -> None:
        self._pipeline.process(frame, ts, frame_id)

    def _on_pipeline_frame(self, frame: np.ndarray) -> None:
        self._latest_frame = frame
        self._window.camera_view.set_frame(frame)
        for mirror in self._frame_mirrors:
            handler = getattr(mirror, "set_frame", None) or getattr(mirror, "push_frame", None)
            if handler is not None:
                handler(frame)

    def _on_pipeline_detection(self, sample, radius_px: float) -> None:
        self._window.camera_view.set_aim_point(sample.x_px, sample.y_px, radius_px=radius_px)
        self._window.camera_view.set_rejected_point(None, None)
        self._window.camera_view.set_status("tracking")
        if sample.x_mm is not None and sample.y_mm is not None:
            self._window.target_view.append_trace_point(sample.x_mm, sample.y_mm)
        if sample.frame_id % self._STATUS_REFRESH_EVERY_N_FRAMES == 0:
            self._refresh_tracking_status()

    def _on_pipeline_miss(self, detection) -> None:
        if detection is not None and detection.rejected_outside_region:
            self._window.camera_view.set_rejected_point(
                detection.x_px, detection.y_px, radius_px=detection.radius_px
            )
            self._window.camera_view.set_aim_point(None, None)
            self._window.camera_view.set_status("rejected")
            return
        self._window.camera_view.set_rejected_point(None, None)
        self._window.camera_view.set_aim_point(None, None)
        self._window.camera_view.set_status("lost")

    def _refresh_tracking_status(self) -> None:
        """Update the header line with the current mm-per-pixel."""
        mm_per_px = self._tracker.mm_per_pixel
        if mm_per_px is None:
            self._window.set_tracking_status("Acquiring target...")
            return
        diameter = self._tracker.circle_diameter_mm
        self._window.set_tracking_status(
            f"Tracking {diameter:.0f} mm circle - {mm_per_px:.3f} mm/px"
        )

    def _on_camera_error(self, message: str) -> None:
        self._window.statusBar().showMessage(f"Camera: {message}", 5000)

    def _on_audio_error(self, message: str) -> None:
        self._window.statusBar().showMessage(f"Audio: {message}", 5000)

    def _on_audio_level(self, level: float) -> None:
        gain = max(0.01, self._preferences.audio_gain)
        scaled = level * gain
        self._window.audio_meter.set_level(scaled)
        for mirror in self._frame_mirrors:
            push = getattr(mirror, "push_audio_level", None)
            if push is not None:
                push(scaled)

    def _on_zero_on_aim_requested(self) -> None:
        if not self._tracker.zero_at_last_sample():
            self._window.statusBar().showMessage(
                "Aim at the target until the trace is live, then try again", 4000
            )
            return
        offset = self._tracker.zero_offset_mm
        self._persist_zero_offset(offset)
        self._window.set_zero_offset_state(True, offset)
        # The trace and on-screen shots were positioned against
        # the old origin. Clearing makes the new zero obvious.
        self._window.target_view.clear_trace()
        self._window.target_view.set_hold_zone(None)
        self._window.statusBar().showMessage(
            f"Trace zeroed: offset ({offset[0]:.1f}, {offset[1]:.1f}) mm", 4000
        )

    def _on_zero_cleared(self) -> None:
        self._tracker.clear_zero_offset()
        self._persist_zero_offset((0.0, 0.0))
        self._window.set_zero_offset_state(False, (0.0, 0.0))
        self._window.target_view.clear_trace()
        self._window.target_view.set_hold_zone(None)
        self._window.statusBar().showMessage("Zero offset cleared", 2000)

    def _persist_zero_offset(self, offset: tuple[float, float]) -> None:
        try:
            save_zero_offset(offset)
        except OSError as exc:
            log.warning("Could not save zero offset: %s", exc)

    def _on_shot_detected(self, event: ShotEvent) -> None:
        result = self._coordinator.handle_shot(event)
        sample = result.sample
        x_mm = sample.x_mm if sample else None
        y_mm = sample.y_mm if sample else None
        score = self._score_for(x_mm, y_mm)

        self._shots_in_view.append(
            _ShotEntry(
                timestamp=event.timestamp,
                x_mm=x_mm or 0.0,
                y_mm=y_mm or 0.0,
                score=score or None,
            )
        )
        self._render_shots()
        self._refresh_stats()

        if self._recorder.is_recording:
            self._recorder.add_shot(
                ts=event.timestamp,
                x_mm=x_mm,
                y_mm=y_mm,
                audio_level=event.audio_level,
                confidence=sample.confidence if sample else 0.0,
                score=score,
            )

    def _on_rescore_requested(self) -> None:
        """Re-score every visible shot against the active target face.

        Useful after switching face on a loaded session. The new
        scores aren't written back to the database, because the
        score there belongs with whatever face was active when the
        shot was recorded. Re-scoring only changes what's
        currently on screen.
        """
        if not self._shots_in_view:
            self._window.statusBar().showMessage("No shots in view to re-score", 3000)
            return
        rescored = 0
        for entry in self._shots_in_view:
            new_score = self._score_for(entry.x_mm, entry.y_mm)
            entry.score = new_score or None
            if new_score:
                rescored += 1
        self._render_shots()
        self._refresh_stats()
        face = self._preferences.target_face
        self._window.statusBar().showMessage(
            f"Re-scored {rescored}/{len(self._shots_in_view)} shots against {face}",
            4000,
        )

    def _score_for(self, x_mm: float | None, y_mm: float | None) -> str:
        """Score a shot against the current target face."""
        if x_mm is None or y_mm is None:
            return ""
        rings = rings_for_face(self._preferences.target_face)
        scoring = [ScoringRing(r.diameter_mm / 2, r.label or "") for r in rings if r.label]
        return score_shot(
            x_mm,
            y_mm,
            scoring,
            shot_diameter_mm=self._preferences.shot_diameter_mm,
        )

    def _render_shots(self) -> None:
        markers = [
            ShotMarker(s.x_mm, s.y_mm, label=str(i + 1), score=s.score or "")
            for i, s in enumerate(self._shots_in_view)
        ]
        self._window.target_view.set_shots(markers)
        self._window.shot_list.set_shots(
            [
                ShotListEntry(
                    index=i,
                    timestamp=s.timestamp,
                    x_mm=s.x_mm,
                    y_mm=s.y_mm,
                    score=s.score,
                )
                for i, s in enumerate(self._shots_in_view)
            ]
        )
        self._window.hero_stats.set_scores([s.score or "" for s in self._shots_in_view])

    def _refresh_stats(self) -> None:
        positions = [(s.x_mm, s.y_mm) for s in self._shots_in_view]
        self._window.hero_stats.update_from_positions(positions)
        self._window.hero_stats.set_trace_points(None)
        self._window.stats_panel.update_from_positions(positions)
        self._window.stats_panel.set_trace_points(None)

    def _on_start_requested(self, name: str) -> None:
        if self._recorder.is_recording:
            return
        self._buffer.clear()
        self._shots_in_view.clear()
        self._window.target_view.clear_trace()
        self._window.target_view.set_trace_segments(release_index=None, shot_index=None)
        self._window.target_view.set_isolate_selected_shot(False)
        self._window.target_view.set_hold_zone(None)
        self._render_shots()
        self._refresh_stats()

        sid = self._recorder.start(
            name=name,
            calibration=None,
            app_version=__version__,
        )
        self._window.session_controls.set_active(True)
        self._window.session_controls.set_summary(f"Recording session {sid}")
        self._window.header.set_state("recording")

    def _on_stop_requested(self) -> None:
        if not self._recorder.is_recording:
            return
        sid = self._recorder.stop()
        self._window.session_controls.set_active(False)
        self._window.session_controls.set_summary(
            f"Saved session {sid}" if sid else "No active session"
        )
        self._window.header.set_state("idle")

    def _on_clear_shots_requested(self) -> None:
        if not self._shots_in_view:
            return
        from PySide6.QtWidgets import QMessageBox

        confirm = QMessageBox.question(
            self._window,
            "Clear shots?",
            "Remove all shots from the display? This does not affect saved sessions.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._shots_in_view.clear()
        self._window.target_view.clear_trace()
        self._window.target_view.set_trace_segments(release_index=None, shot_index=None)
        self._window.target_view.set_isolate_selected_shot(False)
        self._window.target_view.set_hold_zone(None)
        self._render_shots()
        self._refresh_stats()
        self._window.statusBar().showMessage("Display cleared", 2000)

    def _apply_preferences(self, prefs: Preferences, *, persist: bool = True) -> None:
        previous = getattr(self, "_preferences", None)
        self._preferences = prefs
        # Keep the window's cached copy in sync so the
        # Preferences dialog opens against what's actually
        # loaded, not the ``Preferences()`` defaults the window
        # started with.
        self._window.set_current_preferences(prefs)
        self._coordinator.update_settings(
            ShotCoordinatorSettings(pre_shot_ms=prefs.pre_shot_ms, post_shot_ms=prefs.post_shot_ms)
        )
        gain = max(0.01, prefs.audio_gain)
        self._audio.update_settings(
            ShotDetectorSettings(
                threshold=prefs.shot_threshold / gain,
                refractory_ms=prefs.shot_refractory_ms,
            )
        )
        self._audio.set_device(prefs.audio_device)

        self._pipeline.set_transform(
            FrameTransformOptions(
                rotation_degrees=prefs.camera_rotation,
                flip_horizontal=prefs.camera_flip_h,
                flip_vertical=prefs.camera_flip_v,
            )
        )

        rings = rings_for_face(prefs.target_face)
        self._window.target_view.set_rings(rings)
        self._window.target_view.set_shot_diameter_mm(prefs.shot_diameter_mm)
        self._window.hero_stats.set_rings(rings)
        self._window.stats_panel.set_rings(rings)
        self._window.audio_meter.set_threshold(prefs.shot_threshold)

        self._tracker.set_circle_diameter_mm(prefs.circle_diameter_mm)
        self._tracker.set_region_fraction(prefs.tracking_region_fraction)
        self._tracker.set_trace_inversion(
            invert_x=prefs.invert_trace_horizontal,
            invert_y=prefs.invert_trace_vertical,
        )
        self._window.camera_view.set_region_fraction(prefs.tracking_region_fraction)

        if (
            previous is not None
            and previous.camera_id != prefs.camera_id
        ):
            if prefs.camera_id is None:
                self._stop_camera()
            else:
                self._start_camera(prefs.camera_id)
            self._persist_camera_selection(prefs.camera_id)

        # Only save when the change came from the user. The
        # initial load and any reloads from disk should not
        # rewrite the file.
        if previous is not None and previous != prefs and persist:
            try:
                save_preferences(prefs)
            except OSError as exc:
                log.warning("Could not save preferences: %s", exc)
            self._settings_watcher.mark_seen()

    def _on_circle_diameter_changed(self, diameter_mm: float) -> None:
        """The marker-sheet dialog or another widget changed the circle diameter."""
        if abs(diameter_mm - self._preferences.circle_diameter_mm) <= 1e-6:
            return
        updated = replace(self._preferences, circle_diameter_mm=diameter_mm)
        self._apply_preferences(updated)

    def _on_settings_file_changed(self, prefs: Preferences) -> None:
        """Apply preferences that were edited externally on disk."""
        previous = getattr(self, "_preferences", None)
        if previous == prefs:
            return
        self._apply_preferences(prefs, persist=False)
        self._window.statusBar().showMessage("Preferences updated from disk", 3000)

    def _open_session_browser(self) -> None:
        dialog = SessionBrowserDialog(self._repo, parent=self._window)
        dialog.open_session.connect(self._load_session_for_replay)
        dialog.exec()

    def _load_session_for_replay(self, session_id: int) -> None:
        if self._recorder.is_recording:
            self._window.statusBar().showMessage("Stop recording before opening a session", 4000)
            return
        # We only load shots here. Each shot's trace is loaded on
        # selection. Full traces can be large, and most users want
        # the window around a specific shot rather than the whole
        # session.
        shots = self._repo.list_shots(session_id)

        self._current_view_session_id = session_id
        self._window.target_view.clear_trace()
        self._window.target_view.set_trace_segments(release_index=None, shot_index=None)
        self._window.target_view.set_isolate_selected_shot(False)
        self._window.target_view.set_hold_zone(None)
        self._shots_in_view = [
            _ShotEntry(
                timestamp=s.ts,
                x_mm=s.x_mm or 0.0,
                y_mm=s.y_mm or 0.0,
                score=s.score or None,
            )
            for s in shots
        ]
        self._render_shots()
        self._refresh_stats()
        self._window.replay_controls.set_enabled(False)

    def _on_shot_selected(self, index: int) -> None:
        self._window.target_view.set_selected_shot(index)
        if self._current_view_session_id is None:
            return
        shots = self._repo.list_shots(self._current_view_session_id)
        if index < 0 or index >= len(shots):
            return
        prefs = self._preferences
        window = self._replay.shot_window(
            self._current_view_session_id,
            shots[index],
            pre_ms=prefs.pre_shot_ms,
            post_ms=prefs.post_shot_ms,
        )
        self._player.load(window.samples)
        self._window.target_view.set_trace_segments(
            release_index=window.release_index,
            shot_index=window.split_index,
        )
        self._window.target_view.set_isolate_selected_shot(True)
        points = [(s.x_mm or 0.0, s.y_mm or 0.0) for s in window.samples if s.x_mm is not None]
        self._window.target_view.set_trace(points)
        # Trace stats use the pre-shot portion of the window only.
        # That's the part where the shooter was holding rather than
        # reacting to recoil.
        pre_points = points[: window.split_index + 1] if window.split_index is not None else points
        self._window.hero_stats.set_trace_points(pre_points)
        self._window.stats_panel.set_trace_points(pre_points)
        if pre_points:
            stats = compute_trace_stats(pre_points)
            self._window.target_view.set_hold_zone(
                (stats.mean_x_mm, stats.mean_y_mm), stats.hold_tremor_mm
            )
        else:
            self._window.target_view.set_hold_zone(None)
        self._window.replay_controls.set_enabled(bool(window.samples))

    def _on_prefs_dialog_opened(self, dialog) -> None:
        self._register_frame_mirror(dialog)
        if self._latest_frame is not None:
            dialog.push_frame(self._latest_frame)
        dialog.camera_property_changed.connect(self._on_camera_property_changed)
        dialog.camera_changed.connect(self._on_camera_chosen_in_dialog)
        dialog.refresh_devices_requested.connect(
            lambda: self._refresh_dialog_devices(dialog)
        )
        dialog.optimise_requested.connect(self._on_optimise_requested)
        dialog.reset_detector_requested.connect(self._on_reset_detector_requested)

        # Remember which camera was running before the dialog
        # opened so we can revert if the user cancels. The saved
        # state only changes when the dialog emits ``saved`` (the
        # Save button). Any other close path (Cancel, the OS close
        # button, Escape) restores the previous capture.
        original_index = self._preferences.camera_id
        saved = {"committed": False}

        dialog.saved.connect(lambda _prefs: saved.__setitem__("committed", True))
        dialog.finished.connect(
            lambda _r: self._revert_camera_after_dialog(original_index, saved["committed"])
        )

        # Sync the live capture to whatever the dialog ended up
        # pre-selecting. The dialog matches the saved camera by
        # *name* against the live list of devices, which can
        # resolve to a different integer index than
        # ``prefs.camera_id`` if a new USB device shifted the
        # order. Without this sync the preview would silently
        # show whichever device sits at the stale saved index.
        dialog_index = dialog.selected_camera_index()
        if dialog_index != self._camera_device_index():
            if dialog_index is None:
                self._stop_camera()
            else:
                self._start_camera(dialog_index)

    def _refresh_dialog_devices(self, dialog) -> None:
        """Re-enumerate cameras and microphones for the open Preferences dialog.

        Called when the user clicks "Refresh" in the dialog.
        ``QMediaDevices`` picks up devices plugged in after
        launch, which the cached enumeration wouldn't otherwise
        reflect.
        """
        cameras, mics = self._device_options()
        dialog.set_camera_options(cameras)
        dialog.set_audio_options(mics)

    def _revert_camera_after_dialog(
        self,
        original_index: int | None,
        committed: bool,
    ) -> None:
        """Undo any camera change the user made if the dialog wasn't saved.

        While the dialog is open, picking a different camera in
        the combo replaces the running capture so the preview
        reflects the choice. If the user clicks Cancel (or
        closes the dialog any other way), the capture has to
        revert to whatever was running when the dialog opened.
        """
        if committed:
            return
        current_index = self._camera_device_index() if self._camera else None
        if current_index == original_index:
            return
        if original_index is None:
            self._stop_camera()
        else:
            self._start_camera(original_index)

    def _camera_device_index(self) -> int | None:
        """Return the device index of the running capture, or ``None``."""
        cam = self._camera
        if cam is None:
            return None
        return cam.device_index

    def _on_camera_chosen_in_dialog(self, new_index: object) -> None:
        """Swap the live capture so the embedded preview shows the chosen camera.

        Save isn't required. The dialog emits this on every user
        pick so the preview reacts immediately. ``None`` means
        "no camera", which stops the running capture so the
        preview goes blank rather than continuing to show frames
        from the previous device.
        """
        if new_index is None:
            self._stop_camera()
            self._window.set_tracking_status("No camera selected")
            return
        try:
            index = int(new_index)
        except (TypeError, ValueError):
            return
        self._start_camera(index)

    def _on_camera_property_changed(self, name: str, value: object) -> None:
        if self._camera is None:
            return
        # ``value`` is float | None at runtime. The dialog's signal types
        # it loosely so Qt can carry None.
        self._camera.set_property(name, value if value is not None else None)

    def _on_optimise_requested(self) -> None:
        if self._latest_frame is None:
            self._window.statusBar().showMessage(
                "No camera frame available to optimise from", 4000
            )
            return
        new_settings, score = optimise_detector_settings(
            self._latest_frame, self._tracker.detector.settings
        )
        if new_settings is None:
            self._window.statusBar().showMessage(
                "Could not find a stable target in the current frame", 4000
            )
            return
        self._tracker.detector.settings = new_settings
        try:
            save_detector_settings(new_settings)
        except OSError as exc:
            log.warning("Could not save detector settings: %s", exc)
        self._window.statusBar().showMessage(
            f"Tracking optimised (confidence {score:.2f})", 4000
        )

    def _on_reset_detector_requested(self) -> None:
        defaults = DetectorSettings(region_fraction=self._preferences.tracking_region_fraction)
        self._tracker.detector.settings = defaults
        clear_detector_settings()
        self._window.statusBar().showMessage("Detector reset to defaults", 3000)

    def _register_frame_mirror(self, dialog) -> None:
        """Forward live frames and audio levels to ``dialog`` until it closes."""
        self._frame_mirrors.append(dialog)
        dialog.finished.connect(
            lambda _r, d=dialog: self._frame_mirrors.remove(d) if d in self._frame_mirrors else None
        )
