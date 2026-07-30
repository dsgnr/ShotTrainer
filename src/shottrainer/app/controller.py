"""Coordinates camera capture, tracking, audio, storage and the UI."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication

from shottrainer import __version__
from shottrainer.app.preferences import Preferences
from shottrainer.app.target_faces import face_for_name, get_face, list_target_faces, rings_for_face
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
from shottrainer.tracking.detector_tuning import ImageAdjustment, optimise_detector_settings
from shottrainer.tracking.frame_ops import adjust_image, transform_frame
from shottrainer.tracking.models import Detection, TrackingSample
from shottrainer.tracking.tracker import Tracker
from shottrainer.ui.main_window import MainWindow
from shottrainer.ui.session_browser import SessionBrowserDialog
from shottrainer.ui.shot_list import ShotListEntry
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


@dataclass(frozen=True, slots=True)
class _ShotEntry:
    """One shot in the current on-screen list."""

    timestamp: float
    x_mm: float
    y_mm: float
    score: str | None = None


class _FrameMirror(Protocol):
    """Anything that wants to receive live frames and audio levels.

    The Preferences dialog implements this. The controller hands
    each live frame and audio level out to every mirror currently
    open. Defined as a :class:`Protocol` so the dialog doesn't
    have to inherit from anything for the controller's typing to
    be useful.
    """

    def push_frame(self, frame_bgr: np.ndarray) -> None:
        """Receive the latest BGR camera frame."""

    def push_audio_level(self, level: float) -> None:
        """Receive the latest audio level (0..1)."""


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

    # Internal signal used to hop the per-frame result from the
    # camera worker thread to the GUI thread. The capture
    # pipeline runs on the worker so contour detection and the
    # rolling-average updates don't tie up the GUI's event loop.
    # The slot on the other end only does widget repaints, which
    # have to run on the GUI thread anyway.
    # Carries ``(frame, sample_or_None, last_radius_px,
    # last_detection_or_None)``.
    _frame_processed = Signal(object, object, float, object)

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
            # Pipeline callbacks are deliberate no-ops. The
            # controller reacts to ``_frame_processed`` instead so
            # widget updates are guaranteed to land on the GUI
            # thread. The pipeline still owns the buffer append
            # and the recorder write (both safe in the way
            # they're used here), which can stay on the worker
            # thread.
            on_frame=lambda _frame: None,
            on_detection=lambda _sample, _radius: None,
            on_no_detection=lambda _detection: None,
        )

        self._player = TracePlayer(self)
        self._current_view_session_id: int | None = None
        self._shots_in_view: list[_ShotEntry] = []
        self._frame_mirrors: list[_FrameMirror] = []  # dialogs that want live frames
        self._camera_popout = None  # enlarged camera preview dialog
        self._active_prefs_dialog = None  # set while the Preferences dialog is open
        self._frame_transform: FrameTransformOptions | None = None
        self._latest_frame: np.ndarray | None = None
        # The frame the pipeline saw before the user's
        # brightness/contrast adjustment ran on it. Used by the
        # auto-optimiser so successive clicks don't compound the
        # current adjustment on top of the previous one.
        self._latest_unadjusted_frame: np.ndarray | None = None
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
        """Connect every UI signal to its controller slot.

        Centralising the connections here means the controller
        is a single place to look for who reacts to what.
        Subclasses and tests can audit the connections at a
        glance.
        """
        sc = self._window.session_controls
        sc.start_requested.connect(self._on_start_requested)
        sc.stop_requested.connect(self._on_stop_requested)
        sc.clear_shots_requested.connect(self._on_clear_shots_requested)

        rc = self._window.replay_controls
        rc.play_clicked.connect(self._on_replay_play)
        rc.pause_clicked.connect(self._on_replay_pause)
        rc.reset_clicked.connect(self._on_replay_reset)
        rc.scrubbed.connect(self._player.seek_fraction)

        self._player.index_changed.connect(self._window.target_view.set_playhead_index)
        self._player.progress.connect(rc.set_progress)
        # When playback finishes naturally the player flips
        # ``is_playing`` to false. Reflect that in the button so
        # the next click plays again from the start rather than
        # pausing an already-stopped player.
        self._player.finished.connect(lambda: rc.set_playing(False))

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

        # ``_frame_processed`` is emitted from the camera worker
        # thread. Qt queues the slot call onto the GUI thread
        # automatically because this ``QObject`` was created
        # there. All widget updates land on the right thread
        # without the controller having to know about thread
        # affinity.
        self._frame_processed.connect(self._on_frame_processed)

        self._window._expand_button.clicked.connect(self._on_camera_popout_requested)

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
        """Stop any running capture and bring up a fresh one.

        Always builds a new :class:`CameraCapture` instance
        because the worker is single-use, and reusing it would
        risk a stale thread reference. Image controls
        (brightness, contrast) live in the capture pipeline
        rather than at the camera, so they aren't part of the
        device config.
        """
        self._stop_camera()
        cam = CameraCapture(self._camera_config_from_prefs(device_index))
        # ``DirectConnection`` keeps the per-frame work
        # (transform, detect, smoothing update) on the camera's
        # worker thread. Without it Qt would queue every frame
        # onto the GUI thread, where at 120 fps the detector
        # would fight the live preview's repaint and the queue
        # would back up. The slot itself emits a signal back to
        # the GUI thread for the widget updates that actually
        # need to run there.
        cam.frame_ready.connect(self._on_frame, type=Qt.ConnectionType.DirectConnection)
        cam.error.connect(self._on_camera_error)
        cam.start()
        self._camera = cam

    def _camera_config_from_prefs(self, device_index: int) -> CameraConfig:
        """Build a :class:`CameraConfig` from preferences for ``device_index``.

        ``CameraConfig`` only carries device-side options (index,
        backend, requested resolution and frame rate). The image
        controls are applied in software inside the capture
        pipeline, so they don't show up here.
        """
        return CameraConfig(device_index=device_index)

    def _stop_camera(self) -> None:
        """Stop the worker thread and reset the camera view's status pill."""
        if self._camera is not None:
            self._camera.stop()
            self._camera = None
            self._window.camera_view.set_status("idle")

    def _device_options(self) -> tuple[list[tuple[int, str]], list[str]]:
        """List cameras and microphones for the Preferences dialog.

        The camera list is cached so
        :meth:`_persist_camera_selection` can look up a label by
        index later without going to the device tree again.
        """
        cameras = list_available_cameras() or [(0, "Camera 0")]
        mics = list_audio_inputs()
        # Cache so ``_persist_camera_selection`` doesn't re-probe.
        self._cached_camera_options = cameras
        return cameras, mics

    def _on_frame(self, frame: np.ndarray, ts: float, frame_id: int) -> None:
        """Camera signal slot, called for every incoming frame.

        Runs on the camera worker thread (because of the
        ``DirectConnection``), so detection, the running-average
        update, the buffer append and the recorder write all
        happen off the GUI thread. Only the resulting widget
        updates are passed across via ``_frame_processed``.

        The frame is converted to greyscale and run through the
        per-frame transforms (rotation, flip, brightness,
        contrast) before the pipeline sees it. The detector
        ignores colour anyway, and reusing the single-channel
        buffer for the preview avoids a second conversion in
        the camera widget.
        """
        emit_buffer = frame  # the camera owns the original buffer
        owns_copy = False
        if frame.ndim == 3 and frame.shape[2] == 3:
            emit_buffer = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            owns_copy = True
        opts = self._frame_transform
        if opts is not None and (opts.rotation_degrees or opts.flip_horizontal or opts.flip_vertical):
            transformed = transform_frame(
                emit_buffer,
                rotation_degrees=opts.rotation_degrees,
                flip_horizontal=opts.flip_horizontal,
                flip_vertical=opts.flip_vertical,
            )
            if transformed is not emit_buffer:
                emit_buffer = transformed
                owns_copy = True
        # Snapshot the pre-adjustment frame for the auto-tuner so
        # repeated clicks don't compound the current
        # brightness/contrast on top of itself. ``ascontiguousarray``
        # decouples the snapshot from any later in-place writes
        # the camera worker might do to ``frame``.
        self._latest_unadjusted_frame = (
            emit_buffer if owns_copy else np.ascontiguousarray(emit_buffer)
        )
        if opts is not None and (opts.brightness != 0.0 or opts.contrast != 1.0):
            adjusted = adjust_image(
                emit_buffer, brightness=opts.brightness, contrast=opts.contrast
            )
            if adjusted is not emit_buffer:
                emit_buffer = adjusted
                owns_copy = True
        sample = self._pipeline.process(emit_buffer, ts, frame_id)
        # Snapshot the tracker state so the GUI handler reads
        # consistent values even though the worker thread might
        # keep going. Copy the frame only when nothing already
        # allocated a fresh buffer above. The cross-thread emit
        # has to outlive ``frame``, which the camera worker may
        # reuse for the next read.
        last_radius_px = self._tracker.last_radius_px
        last_detection = self._tracker.last_detection
        out = emit_buffer if owns_copy else emit_buffer.copy()
        self._frame_processed.emit(out, sample, last_radius_px, last_detection)

    def _on_frame_processed(
        self,
        frame: np.ndarray,
        sample: TrackingSample | None,
        last_radius_px: float,
        last_detection: Detection | None,
    ) -> None:
        """GUI-thread handler for the per-frame pipeline result.

        Updates the camera preview, the tracking-status badge and
        the live trace. Runs after the heavy detection work has
        already finished on the worker thread.
        """
        self._latest_frame = frame
        self._window.camera_view.set_frame(frame)
        for mirror in self._frame_mirrors:
            mirror.push_frame(frame)

        if sample is None:
            if last_detection is not None and last_detection.rejected_outside_region:
                self._window.camera_view.set_rejected_point(
                    last_detection.x_px,
                    last_detection.y_px,
                    radius_px=last_detection.radius_px,
                )
                self._window.camera_view.set_aim_point(None, None)
                self._window.camera_view.set_status("rejected")
                return
            self._window.camera_view.set_rejected_point(None, None)
            self._window.camera_view.set_aim_point(None, None)
            self._window.camera_view.set_status("lost")
            return

        self._window.camera_view.set_aim_point(
            sample.x_px, sample.y_px, radius_px=last_radius_px
        )
        self._window.camera_view.set_rejected_point(None, None)
        self._window.camera_view.set_status("tracking")
        if sample.x_mm is not None and sample.y_mm is not None:
            self._window.target_view.append_trace_point(sample.x_mm, sample.y_mm)
        if sample.frame_id % self._STATUS_REFRESH_EVERY_N_FRAMES == 0:
            self._refresh_tracking_status()

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
        """Show a brief camera error in the status bar."""
        self._window.statusBar().showMessage(f"Camera: {message}", 5000)

    def _on_audio_error(self, message: str) -> None:
        """Show a brief audio error in the status bar."""
        self._window.statusBar().showMessage(f"Audio: {message}", 5000)

    def _on_audio_level(self, level: float) -> None:
        """Scale the incoming audio level by the user's gain, then push it to the meter and any frame mirrors."""
        gain = max(0.01, self._preferences.audio_gain)
        scaled = level * gain
        self._window.audio_meter.set_level(scaled)
        for mirror in self._frame_mirrors:
            mirror.push_audio_level(scaled)

    def _on_zero_on_aim_requested(self) -> None:
        """Lock the most recent aim point as the trace's origin.

        If the detector hasn't reported a sample yet we tell the
        user via the status bar instead. Otherwise we save the
        new offset and clear the trace so the new origin is
        obvious straight away.
        """
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
        """Drop the zero offset, save it, and refresh the UI."""
        self._tracker.clear_zero_offset()
        self._persist_zero_offset((0.0, 0.0))
        self._window.set_zero_offset_state(False, (0.0, 0.0))
        self._window.target_view.clear_trace()
        self._window.target_view.set_hold_zone(None)
        self._window.statusBar().showMessage("Zero offset cleared", 2000)

    def _persist_zero_offset(self, offset: tuple[float, float]) -> None:
        """Save the zero offset to disk. Log and carry on if it fails."""
        try:
            save_zero_offset(offset)
        except OSError as exc:
            log.warning("Could not save zero offset: %s", exc)

    def _on_shot_detected(self, event: ShotEvent) -> None:
        """Handle a detected shot. Save it if a session is recording and update the screen.

        Asks :class:`ShotCoordinator` for the trace sample
        nearest the shot's timestamp, scores it against the
        active face, adds it to ``_shots_in_view``, and (if a
        recording is in progress) saves it to the database.
        """
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
        new_entries: list[_ShotEntry] = []
        for entry in self._shots_in_view:
            new_score = self._score_for(entry.x_mm, entry.y_mm)
            new_entries.append(replace(entry, score=new_score or None))
            if new_score:
                rescored += 1
        self._shots_in_view = new_entries
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
        face = get_face(self._preferences.target_face)
        if face is None:
            return ""
        scoring = sorted(
            (ScoringRing(r.diameter_mm / 2, r.label or "") for r in face.rings if r.label),
            key=lambda r: r.radius_mm,
        )
        return score_shot(
            x_mm,
            y_mm,
            scoring,
            shot_diameter_mm=self._preferences.shot_diameter_mm,
            scoring_direction=face.scoring_direction,
        )

    def _render_shots(self) -> None:
        """Push the in-memory shot list out to every widget that shows it."""
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
        """Recompute group statistics for the current shot list."""
        positions = [(s.x_mm, s.y_mm) for s in self._shots_in_view]
        self._window.hero_stats.update_from_positions(positions)
        self._window.hero_stats.set_trace_points(None)

    def _on_start_requested(self, name: str) -> None:
        """Open a new recording session.

        Resets the trace buffer, the on-screen shot list and the
        replay overlays so the new session starts clean. Ignored
        when a recording is already in progress. The caller is
        expected to ``stop`` first.
        """
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
            app_version=__version__,
        )
        self._window.session_controls.set_active(True)
        self._window.session_controls.set_summary(f"Recording session {sid}")
        self._window.header.set_state("recording")

    def _on_stop_requested(self) -> None:
        """Stop the current recording, if any."""
        if not self._recorder.is_recording:
            return
        sid = self._recorder.stop()
        self._window.session_controls.set_active(False)
        self._window.session_controls.set_summary(
            f"Saved session {sid}" if sid else "No active session"
        )
        self._window.header.set_state("idle")

    def _on_clear_shots_requested(self) -> None:
        """Confirm with the user, then drop the on-screen shot list.

        Saved sessions aren't touched. This only clears what's
        currently rendered. The confirmation prompt is the only
        guard against an accidental click.
        """
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
        """Push a fresh :class:`Preferences` into every dependent service.

        Acts as the one place that handles "the user (or the settings
        file) changed something". Updates the tracker, the audio
        listener, the shot coordinator's pre/post window, the
        target view's rings, the camera's image transform and
        the window's cached preferences. Saves to disk only when
        ``persist=True`` and the change actually originated from
        the user, so the settings-file watcher doesn't bounce
        external edits back at itself.
        """
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

        self._frame_transform = self._build_transform_options(prefs)

        rings = rings_for_face(prefs.target_face)
        self._window.target_view.set_rings(rings)
        self._window.target_view.set_shot_diameter_mm(prefs.shot_diameter_mm)
        self._window.hero_stats.set_rings(rings)
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
        """Open the session-browser dialog, modal to the main window."""
        dialog = SessionBrowserDialog(self._repo, parent=self._window)
        dialog.open_session.connect(self._load_session_for_replay)
        dialog.exec()

    def _load_session_for_replay(self, session_id: int) -> None:
        """Load a saved session's shots into the view for replay.

        The trace itself is loaded one shot at a time when the
        user picks a shot, rather than eagerly. A whole
        session's trace can be megabytes, where one shot's window
        is a few KB.
        """
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
        self._window.replay_controls.set_window_duration_ms(None)

    def _on_replay_play(self) -> None:
        """Start playback and tell the controls to show the pause glyph."""
        self._player.play()
        self._window.replay_controls.set_playing(self._player.is_playing)

    def _on_replay_pause(self) -> None:
        """Pause playback and flip the controls back to the play glyph."""
        self._player.pause()
        self._window.replay_controls.set_playing(False)

    def _on_replay_reset(self) -> None:
        """Stop the player and flip the controls back to the play glyph."""
        self._player.stop()
        self._window.replay_controls.set_playing(False)

    def _on_shot_selected(self, index: int) -> None:
        """Load the chosen shot's window into the replay UI.

        Pulls the trace samples bracketing the shot, isolates the
        shot's marker, configures the three-colour ramp around
        the release window, and updates the hold-zone overlay
        from the pre-shot statistics.
        """
        self._window.target_view.set_selected_shot(index)
        if self._current_view_session_id is None:
            return
        if index < 0 or index >= len(self._shots_in_view):
            return
        prefs = self._preferences
        window = self._replay.shot_window(
            self._current_view_session_id,
            self._shots_in_view[index].timestamp,
            pre_ms=prefs.pre_shot_ms,
            post_ms=prefs.post_shot_ms,
        )
        self._player.load(window.samples)
        # ``load`` rewinds the player to a paused state. Snap the
        # play/pause button back to the play glyph so the user
        # sees they need to start the new replay manually.
        self._window.replay_controls.set_playing(False)
        self._window.target_view.set_trace_segments(
            release_index=window.release_index,
            shot_index=window.split_index,
        )
        self._window.target_view.set_isolate_selected_shot(True)
        points = [(s.x_mm or 0.0, s.y_mm or 0.0) for s in window.samples if s.x_mm is not None]
        self._window.target_view.set_trace(points)
        self._window.replay_controls.set_window_duration_ms(
            int(prefs.pre_shot_ms) + int(prefs.post_shot_ms)
        )
        # Trace stats use the pre-shot portion of the window only.
        # That's the part where the shooter was holding rather than
        # reacting to recoil.
        pre_points = points[: window.split_index + 1] if window.split_index is not None else points
        self._window.hero_stats.set_trace_points(pre_points)
        if pre_points:
            stats = compute_trace_stats(pre_points)
            self._window.target_view.set_hold_zone(
                (stats.mean_x_mm, stats.mean_y_mm), stats.hold_tremor_mm
            )
        else:
            self._window.target_view.set_hold_zone(None)
        self._window.replay_controls.set_enabled(bool(window.samples))

    def _on_prefs_dialog_opened(self, dialog) -> None:
        """Hook the controller into a freshly opened Preferences dialog.

        Adds the dialog as a frame mirror so the embedded preview
        ticks live, connects every dialog-side signal to its
        controller slot, and arranges to revert the camera
        selection if the user closes without saving.
        """
        self._register_frame_mirror(dialog)
        self._active_prefs_dialog = dialog
        dialog.finished.connect(self._on_prefs_dialog_closed)
        if self._latest_frame is not None:
            dialog.push_frame(self._latest_frame)
        dialog.camera_property_changed.connect(self._on_camera_property_changed)
        dialog.camera_transform_changed.connect(self._on_camera_transform_changed)
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
        original_prefs = self._preferences
        saved = {"committed": False}

        dialog.saved.connect(lambda _prefs: saved.__setitem__("committed", True))
        dialog.finished.connect(
            lambda _r: self._revert_camera_after_dialog(original_index, saved["committed"])
        )
        dialog.finished.connect(
            lambda _r: self._revert_transform_after_dialog(original_prefs, saved["committed"])
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

    def _revert_transform_after_dialog(
        self,
        original_prefs: Preferences,
        committed: bool,
    ) -> None:
        """Undo unsaved rotation, flip and image-control changes on cancel.

        While the dialog is open the controller updates
        ``self._preferences`` and the live frame transform on
        every slider movement and rotation/flip toggle so the
        preview reflects the new values. On a non-Save close
        both have to revert to what was loaded when the dialog
        opened. The Save path is covered by
        :meth:`_apply_preferences` with a fresh
        :class:`Preferences`.
        """
        if committed:
            return
        self._preferences = original_prefs
        self._frame_transform = self._build_transform_options(original_prefs)

    def _camera_device_index(self) -> int | None:
        """Return the device index of the running capture, or ``None``."""
        cam = self._camera
        if cam is None:
            return None
        return cam.device_index

    def _on_camera_chosen_in_dialog(self, new_index: int | None) -> None:
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

    def _on_camera_property_changed(self, name: str, value: float | None) -> None:
        """Push a slider change into the live transform straight away.

        The dialog fires this on every slider movement so the
        embedded preview shows the change at once. The new value
        goes into the controller's frame transform so both the
        preview and the detector see the corrected frame.
        Nothing is saved to disk until the user clicks Save. The
        cancel path leaves the previous values in place via
        :meth:`_apply_preferences`.
        """
        if value is None:
            return
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return
        if name == "brightness":
            self._preferences = replace(self._preferences, camera_brightness=numeric)
        elif name == "contrast":
            self._preferences = replace(self._preferences, camera_contrast=numeric)
        else:
            return
        self._frame_transform = self._build_transform_options(self._preferences)

    def _on_camera_transform_changed(
        self, rotation: int, flip_h: bool, flip_v: bool
    ) -> None:
        """Apply a rotation or flip change from the open Preferences dialog.

        Mirrors the brightness/contrast path. The controller's
        frame transform is updated live so the embedded preview
        reflects what saving will do, and nothing is written to
        disk until the user clicks Save.
        """
        self._preferences = replace(
            self._preferences,
            camera_rotation=rotation,
            camera_flip_h=flip_h,
            camera_flip_v=flip_v,
        )
        self._frame_transform = self._build_transform_options(self._preferences)

    @staticmethod
    def _build_transform_options(prefs: Preferences) -> FrameTransformOptions:
        """Build the controller's frame transform from a preferences object."""
        return FrameTransformOptions(
            rotation_degrees=prefs.camera_rotation,
            flip_horizontal=prefs.camera_flip_h,
            flip_vertical=prefs.camera_flip_v,
            brightness=prefs.camera_brightness,
            contrast=prefs.camera_contrast,
        )

    def _on_optimise_requested(self) -> None:
        """Run the auto-tuner against the latest frame.

        The grid is small enough now (a few dozen detector calls
        on a typical greyscale frame) that running it inline
        only blocks the GUI for around 100 ms on a clean frame.
        That's well below the threshold where a user notices a
        freeze, and it side-steps the GIL contention that
        threading runs into when both the camera worker and the
        optimiser are calling into ``cv2`` at the same time.
        """
        source = self._latest_unadjusted_frame
        if source is None:
            self._set_detector_status(
                "No camera frame available to optimise from", kind="warning"
            )
            return

        self._set_optimise_button_enabled(False)
        self._set_detector_status("Optimising tracking...", kind="info")
        # Force the disabled-button state and the status label to
        # paint before the search starts. Without this, the
        # ``Optimising...`` label only appears once the slot
        # returns.
        QApplication.processEvents()

        base_settings = self._tracker.detector.settings
        try:
            new_settings, adjustment, score = optimise_detector_settings(
                source, base_settings
            )
        except Exception:
            log.exception("Auto-optimise failed")
            new_settings, adjustment, score = None, None, 0.0

        self._on_optimise_finished(new_settings, adjustment, score)

    def _on_optimise_finished(
        self,
        new_settings: DetectorSettings | None,
        adjustment: ImageAdjustment | None,
        score: float,
    ) -> None:
        """Apply the optimiser's result and refresh the dialog."""
        self._set_optimise_button_enabled(True)
        if new_settings is None or adjustment is None:
            self._set_detector_status(
                "Could not find a stable target in the current frame", kind="warning"
            )
            return
        previous_settings = self._tracker.detector.settings
        previous_brightness = self._preferences.camera_brightness
        previous_contrast = self._preferences.camera_contrast
        unchanged = (
            new_settings == previous_settings
            and adjustment.brightness == previous_brightness
            and adjustment.contrast == previous_contrast
        )
        self._tracker.detector.settings = new_settings
        try:
            save_detector_settings(new_settings)
        except OSError as exc:
            log.warning("Could not save detector settings: %s", exc)
        # Push the suggested brightness/contrast back into
        # preferences so the live pipeline picks them up on the
        # next frame.
        self._preferences = replace(
            self._preferences,
            camera_brightness=adjustment.brightness,
            camera_contrast=adjustment.contrast,
        )
        self._frame_transform = self._build_transform_options(self._preferences)
        # If the Preferences dialog is open, snap its sliders so
        # the user can see what the optimiser settled on.
        dialog = self._active_prefs_dialog
        if dialog is not None:
            dialog.set_image_controls(adjustment.brightness, adjustment.contrast)
        if unchanged:
            self._set_detector_status(
                f"Already optimal (confidence {score:.2f})", kind="info"
            )
        else:
            self._set_detector_status(
                f"Tracking optimised (confidence {score:.2f})", kind="success"
            )

    def _set_optimise_button_enabled(self, enabled: bool) -> None:
        """Enable or disable the Auto-optimise button on the open dialog."""
        dialog = self._active_prefs_dialog
        if dialog is not None:
            dialog.set_optimise_enabled(enabled)

    def _on_reset_detector_requested(self) -> None:
        """Reset the detector to defaults and delete the saved file."""
        defaults = DetectorSettings(region_fraction=self._preferences.tracking_region_fraction)
        self._tracker.detector.settings = defaults
        clear_detector_settings()
        self._set_detector_status("Detector reset to defaults", kind="info")

    def _set_detector_status(self, text: str, *, kind: str) -> None:
        """Show a detector status message in the status bar and the dialog."""
        timeout = 4000 if kind != "info" else 3000
        self._window.statusBar().showMessage(text, timeout)
        dialog = self._active_prefs_dialog
        if dialog is not None:
            dialog.set_detector_status(text, kind=kind)

    def _on_prefs_dialog_closed(self, _result: int) -> None:
        """Drop the dialog reference once it closes."""
        self._active_prefs_dialog = None

    def _register_frame_mirror(self, dialog) -> None:
        """Forward live frames and audio levels to ``dialog`` until it closes."""
        self._frame_mirrors.append(dialog)
        dialog.finished.connect(
            lambda _r, d=dialog: self._frame_mirrors.remove(d) if d in self._frame_mirrors else None
        )

    def _on_camera_popout_requested(self) -> None:
        """Open (or raise) the enlarged camera preview dialog."""
        from shottrainer.ui.camera_popout import CameraPopout

        if self._camera_popout is not None and self._camera_popout.isVisible():
            self._camera_popout.raise_()
            self._camera_popout.activateWindow()
            return

        popout = CameraPopout(self._window)
        self._camera_popout = popout

        # Push the current frame immediately so it's not blank on open.
        if self._latest_frame is not None:
            popout.view.set_frame(self._latest_frame)
            popout.view.set_region_fraction(self._window.camera_view._region_fraction)
            h, w = self._latest_frame.shape[:2]
            popout.set_resolution(w, h)
        # Mirror live frames into the popout's view.
        self._frame_mirrors.append(popout.view)
        popout.finished.connect(self._on_camera_popout_closed)
        popout.show()
        popout.raise_()
        popout.activateWindow()

    def _on_camera_popout_closed(self, _result: int) -> None:
        """Clean up when the popout dialog closes."""
        if self._camera_popout is not None:
            view = self._camera_popout.view
            if view in self._frame_mirrors:
                self._frame_mirrors.remove(view)
            self._camera_popout = None
