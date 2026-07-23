"""Write golden fixtures from the Python implementation for the Rust tests."""

from __future__ import annotations

import base64
import json
import math
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "testdata" / "golden"


def encode_number(value: float | None) -> float | str | None:
    """JSON has no non-finite numbers, so they are written as strings."""
    if value is None or math.isfinite(value):
        return value
    if math.isnan(value):
        return "nan"
    return "inf" if value > 0 else "-inf"


def scoring() -> dict:
    from shottrainer.services.scoring import ScoringRing, label_to_value, score_shot, total_score

    rings = [ScoringRing(r, str(n)) for r, n in [(5.0, 10), (10.0, 9), (20.0, 8), (40.0, 7)]]
    ring_sets = {
        "standard": [(r.radius_mm, r.label) for r in rings],
        "empty": [],
        "single": [(10.0, "X")],
        "unsorted": [(20.0, "8"), (5.0, "10"), (10.0, "9")],
    }
    positions = [
        (0.0, 0.0),
        (5.0, 0.0),
        (5.0001, 0.0),
        (0.0, -10.0),
        (14.0, 14.0),
        (100.0, 0.0),
        (-3.0, 4.0),
    ]
    cases = []
    for spec in ring_sets.values():
        rs = [ScoringRing(r, label) for r, label in spec]
        for direction in ("inward", "outward", "other"):
            for diameter in (0.0, 4.5, 11.0):
                for centre in ((0.0, 0.0), (2.0, -3.0)):
                    for x, y in positions:
                        label = score_shot(
                            x,
                            y,
                            rs,
                            shot_diameter_mm=diameter,
                            centre=centre,
                            scoring_direction=direction,
                        )
                        cases.append(
                            {
                                "rings": spec,
                                "direction": direction,
                                "shot_diameter_mm": diameter,
                                "centre": list(centre),
                                "x": x,
                                "y": y,
                                "label": label,
                            }
                        )
    labels = [
        "",
        "X",
        "x",
        "10",
        "9.5",
        "abc",
        " 8",
        "8 ",
        "-1",
        "+5",
        "1e1",
        "inf",
        "-inf",
        "Infinity",
        "nan",
        "1_0",
        "1__0",
        "_1",
        ".5",
        "5.",
        "0x10",
    ]
    return {
        "score_shot": cases,
        "label_to_value": [{"label": s, "value": encode_number(label_to_value(s))} for s in labels],
        "total_score": [
            {"labels": ls, "total": encode_number(total_score(ls))}
            for ls in (
                [],
                ["10", "X", "9"],
                ["10", "abc", ""],
                ["x", "x"],
                ["8.5", "7.5"],
                ["inf"],
                ["inf", "-inf"],
                ["nan", "5"],
                ["-0"],
            )
        ],
    }


def shot_stats() -> dict:
    import random

    from shottrainer.services.shot_stats import (
        compute_stats,
        compute_trace_stats,
        time_inside_radius,
    )

    rng = random.Random(7)
    inputs = {
        "empty": [],
        "one_point": [(3.5, -2.25)],
        "identical": [(1.5, 1.5), (1.5, 1.5)],
        "two_points": [(0.0, 0.0), (3.0, 4.0)],
        "five_points": [(0.0, 0.0), (2.0, 1.0), (-1.5, 3.0), (4.0, -2.0), (0.5, 0.25)],
        "random_200": [(rng.uniform(-15, 15), rng.uniform(-15, 15)) for _ in range(200)],
        "collinear": [(float(i), 2.0 * i + 1.0) for i in range(-3, 6)],
    }
    cases = []
    for name, pts in inputs.items():
        stats = compute_stats(pts)
        trace = compute_trace_stats(pts)
        cases.append(
            {
                "name": name,
                "points": [list(p) for p in pts],
                "stats": {
                    "count": stats.count,
                    "mean_x_mm": stats.mean_x_mm,
                    "mean_y_mm": stats.mean_y_mm,
                    "extreme_spread_mm": stats.extreme_spread_mm,
                    "mean_radius_mm": stats.mean_radius_mm,
                },
                "trace": {
                    "samples": trace.samples,
                    "hold_tremor_mm": trace.hold_tremor_mm,
                    "trace_length_mm": trace.trace_length_mm,
                    "mean_x_mm": trace.mean_x_mm,
                    "mean_y_mm": trace.mean_y_mm,
                },
                "inside": [
                    {
                        "radius_mm": radius,
                        "centre": list(centre),
                        "fraction": time_inside_radius(pts, radius, centre),
                    }
                    for radius in (0.0, 1.0, 5.0, 100.0)
                    for centre in ((0.0, 0.0), (1.0, -1.0))
                ],
            }
        )
    return {"cases": cases}


def trace() -> dict:
    from shottrainer.audio.models import ShotEvent
    from shottrainer.replay.timeline import index_of_nearest, slice_window
    from shottrainer.services.shot_coordinator import ShotCoordinator, ShotCoordinatorSettings
    from shottrainer.services.trace_buffer import TraceBuffer
    from shottrainer.tracking.models import TrackingSample

    def make(times: list[float]) -> list[TrackingSample]:
        return [
            TrackingSample(timestamp=t, x_px=float(i), y_px=2.0 * i, frame_id=i)
            for i, t in enumerate(times)
        ]

    def ref(sample: TrackingSample | None) -> dict | None:
        if sample is None:
            return None
        return {"timestamp": sample.timestamp, "frame_id": sample.frame_id}

    def refs(samples: list[TrackingSample]) -> list[dict]:
        return [ref(s) for s in samples]

    # Every timestamp is a dyadic rational so midpoints are exact and ties are real ties.
    sets = {
        "empty": ([], 6000),
        "one_sample": ([2.5], 6000),
        "ten_even": ([10.0 + 0.5 * i for i in range(10)], 6000),
        "uneven_duplicate": ([0.0, 0.25, 0.75, 0.75, 1.5, 4.0, 4.5], 6000),
        "overflow": ([0.5 * i for i in range(12)], 5),
        "zero_capacity": ([0.0, 1.0, 2.0], 0),
    }

    def queries_for(times: list[float]) -> list[float]:
        found = {0.0, 1.0, 2.5, -1.0}
        for i, t in enumerate(times):
            found.update((t, t - 0.125, t + 0.125))
            if i:
                found.add((times[i - 1] + t) / 2.0)
        if times:
            found.update((times[0] - 1.0, times[-1] + 1.0))
        return sorted(found)

    non_finite = [float("nan"), float("inf"), float("-inf")]
    window_pairs = [
        (0.0, 1.0),
        (0.25, 0.75),
        (0.75, 0.75),
        (1.0, 0.0),
        (4.5, 0.0),
        (-100.0, 100.0),
        (10.0, 12.0),
        (12.25, 20.0),
        (13.0, 11.0),
        (2.5, 2.5),
        (float("-inf"), float("inf")),
        (float("nan"), 5.0),
        (0.0, float("nan")),
    ]
    windows_ms = [
        (0, 0),
        (500, 500),
        (1500, 800),
        (-500, 500),
        (500, -500),
        (-1000, -1000),
        (250, 0),
    ]

    cases = []
    for name, (times, capacity) in sets.items():
        samples = make(times)
        buf = TraceBuffer(capacity)
        buf.extend(samples)
        snapshot = buf.snapshot()
        queries = queries_for(times) + non_finite
        case = {
            "name": name,
            "capacity": capacity,
            "appended": refs(samples),
            "snapshot": refs(snapshot),
            "nearest": [
                {"query": encode_number(q), "result": ref(buf.nearest(q))} for q in queries
            ],
            "windows": [
                {
                    "start": encode_number(a),
                    "end": encode_number(b),
                    "result": refs(buf.window(a, b)),
                }
                for a, b in window_pairs + [(q, q + 1.0) for q in queries[:6]]
            ],
            "timeline_nearest": [
                {"query": encode_number(q), "index": index_of_nearest(snapshot, q)} for q in queries
            ],
            "slices": [
                {
                    "centre": encode_number(c),
                    "pre_ms": pre,
                    "post_ms": post,
                    "result": refs(slice_window(snapshot, c, pre, post)),
                }
                for c in queries
                for pre, post in windows_ms
            ],
        }
        settings_list = [
            ShotCoordinatorSettings(),
            ShotCoordinatorSettings(pre_shot_ms=100, post_shot_ms=100),
            ShotCoordinatorSettings(pre_shot_ms=0, post_shot_ms=0),
            ShotCoordinatorSettings(pre_shot_ms=2000, post_shot_ms=0),
            ShotCoordinatorSettings(pre_shot_ms=-250, post_shot_ms=500),
        ]
        shots = []
        for settings in settings_list:
            coordinator = ShotCoordinator(buf, settings)
            for q in queries:
                result = coordinator.handle_shot(
                    ShotEvent(timestamp=q, audio_level=0.5, sample_rate=48000)
                )
                shots.append(
                    {
                        "pre_shot_ms": settings.pre_shot_ms,
                        "post_shot_ms": settings.post_shot_ms,
                        "timestamp": encode_number(q),
                        "sample": ref(result.sample),
                        "trace": refs(result.trace),
                    }
                )
        case["shots"] = shots
        cases.append(case)
    return {"cases": cases}


def export_csv() -> dict:
    from shottrainer.services.exporter import export_session_csv
    from shottrainer.sessions.database import init_database, make_engine
    from shottrainer.sessions.repository import SessionRepository
    from shottrainer.tracking.models import TrackingSample

    engine = make_engine(":memory:")
    init_database(engine)
    repo = SessionRepository(engine)
    sid = repo.create_session(name="export")
    # Halfway, tiny, negative-rounding-to-zero and large values exercise the
    # fixed-decimal formatting.
    shots = [
        {
            "ts": 0.0005,
            "x_mm": None,
            "y_mm": None,
            "audio_level": 0.00005,
            "confidence": 0.5,
            "score": "",
        },
        {
            "ts": 1.0000005,
            "x_mm": 0.0005,
            "y_mm": -0.0004,
            "audio_level": 0.12345,
            "confidence": 0.99995,
            "score": "10,5",
        },
        {
            "ts": 2.5,
            "x_mm": 2.5e-4,
            "y_mm": -1e-7,
            "audio_level": 1.0,
            "confidence": 0.0,
            "score": 'say "9"',
        },
        {
            "ts": 1234567.8915,
            "x_mm": 1234567.8915,
            "y_mm": -0.0015,
            "audio_level": 2.5,
            "confidence": 1.0,
            "score": "9",
        },
    ]
    for shot in shots:
        repo.add_shot(sid, **shot)
    samples = [
        {
            "timestamp": 0.0,
            "x_px": 0.0005,
            "y_px": -0.0004,
            "x_mm": 1.0,
            "y_mm": -1.0,
            "confidence": 1.0,
            "frame_id": 0,
        },
        {
            "timestamp": 0.1234565,
            "x_px": 12.3455,
            "y_px": -1e-7,
            "x_mm": None,
            "y_mm": None,
            "confidence": 0.00005,
            "frame_id": 7,
        },
        {
            "timestamp": 0.2,
            "x_px": 1e7,
            "y_px": 2.5e-4,
            "x_mm": -1e-7,
            "y_mm": 1e6,
            "confidence": 0.5,
            "frame_id": 1234567,
        },
        {
            "timestamp": 0.3,
            "x_px": 3.0,
            "y_px": 4.0,
            "x_mm": 0.0015,
            "y_mm": 2.0005,
            "confidence": 0.25,
            "frame_id": 1001,
        },
    ]
    repo.append_trace(sid, [TrackingSample(**s) for s in samples])
    with tempfile.TemporaryDirectory() as tmp:
        paths = export_session_csv(repo, sid, Path(tmp))
        files = {p.name: base64.b64encode(p.read_bytes()).decode() for p in paths}
    return {"shots": shots, "samples": samples, "files": files}


def preferences() -> dict:
    import os
    from dataclasses import asdict
    from unittest import mock

    from shottrainer.app import paths
    from shottrainer.app.preferences import Preferences
    from shottrainer.app.settings import _RANGES, load_preferences, save_preferences

    texts: list[tuple[str, str | bytes]] = [
        ("empty object", "{}"),
        ("whitespace object", " \n{ }\n"),
        ("null", "null"),
        ("array", "[]"),
        ("number", "3"),
        ("string", '"x"'),
        ("true", "true"),
        ("invalid json", "not json"),
        ("truncated", '{"camera_id": 1,'),
        ("empty file", ""),
        ("invalid utf-8", b"\xff\xfe"),
        ("unknown keys", '{"camera_id": 1, "unknown_key": true, "other": [1, 2]}'),
        ("duplicate key", '{"camera_id": 1, "camera_id": 4}'),
        (
            "full valid",
            json.dumps(
                {
                    "camera_id": 2,
                    "camera_rotation": 270,
                    "camera_flip_h": True,
                    "camera_flip_v": True,
                    "camera_brightness": -12.5,
                    "camera_contrast": 1.75,
                    "audio_device": "USB Mic \u00e9",
                    "audio_gain": 3.5,
                    "shot_threshold": 0.4,
                    "shot_refractory_ms": 500,
                    "pre_shot_ms": 2000,
                    "post_shot_ms": 1000,
                    "release_window_ms": 300,
                    "target_face": "ten_metre",
                    "shot_diameter_mm": 5.6,
                    "tracking_region_fraction": 0.5,
                    "circle_diameter_mm": 80.0,
                    "invert_trace_horizontal": True,
                    "invert_trace_vertical": True,
                    "show_hold_zone": False,
                }
            ),
        ),
        ("camera id null", '{"camera_id": null}'),
        ("camera id negative", '{"camera_id": -1, "audio_gain": 2}'),
        ("camera id zero", '{"camera_id": 0}'),
        ("camera id int32 max", '{"camera_id": 2147483647}'),
        ("camera id past int32", '{"camera_id": 2147483648}'),
        ("camera id float", '{"camera_id": 1.0}'),
        ("camera id true", '{"camera_id": true}'),
        ("camera id string", '{"camera_id": "1"}'),
        ("camera id exponent", '{"camera_id": 1e2}'),
        ("negative zero int", '{"pre_shot_ms": -0}'),
        ("rotation 90", '{"camera_rotation": 90}'),
        ("rotation 45", '{"camera_rotation": 45}'),
        ("rotation float", '{"camera_rotation": 90.0}'),
        ("integer for float field", '{"audio_gain": 2, "camera_brightness": -5}'),
        ("float for int field", '{"shot_refractory_ms": 400.0}'),
        ("huge int", '{"release_window_ms": 100000000000000000000, "audio_gain": 1e999}'),
        ("nan", '{"shot_threshold": NaN, "shot_diameter_mm": 5.6}'),
        ("infinity", '{"audio_gain": Infinity, "camera_contrast": -Infinity, "pre_shot_ms": 7}'),
        ("nan in string", '{"audio_device": "NaN Infinity", "shot_threshold": NaN}'),
        ("nan for string field", '{"audio_device": NaN}'),
        ("legacy nulls", '{"camera_id": null, "camera_brightness": null, "camera_contrast": null}'),
        ("empty strings", '{"audio_device": "", "target_face": ""}'),
        ("non-bmp string", r'{"audio_device": "mic \ud83c\udfa4"}'),
        ("seventeen digit float", '{"tracking_region_fraction": 0.19862074538694519}'),
    ]
    defaults = asdict(Preferences())
    wrong_types = {
        "camera_id": ["1", 1.5, True, [], {}],
        "camera_rotation": ["90", True, None, 90.5],
        "camera_flip_h": [1, "false", None, 0.0],
        "camera_flip_v": [0, "true", None],
        "camera_brightness": ["1", True, None, []],
        "camera_contrast": ["1", False, None],
        "audio_device": [1, True, None, []],
        "audio_gain": ["1", True, None],
        "shot_threshold": ["0.2", False, None],
        "shot_refractory_ms": ["400", True, None, 400.5],
        "pre_shot_ms": ["1", True, None],
        "post_shot_ms": ["1", False, None],
        "release_window_ms": ["250", True, None],
        "target_face": [1, True, None, {}],
        "shot_diameter_mm": ["4.5", True, None],
        "tracking_region_fraction": ["0.7", True, None],
        "circle_diameter_mm": ["60", True, None],
        "invert_trace_horizontal": [1, "x", None],
        "invert_trace_vertical": [1, "x", None],
        "show_hold_zone": [1, "x", None],
    }
    for key, values in wrong_types.items():
        for i, value in enumerate(values):
            texts.append(
                (f"wrong type {key} {i}", json.dumps({key: value, "shot_diameter_mm": 5.6}))
            )
    for key, (low, high) in _RANGES.items():
        step = 1 if isinstance(low, int) else low / 10
        for label, value in [
            ("below", low - step),
            ("at low", low),
            ("at high", high),
            ("above", high + step),
        ]:
            texts.append((f"range {key} {label}", json.dumps({key: value, "audio_gain": 2.5})))

    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "settings.json"
        for name, text in texts:
            if isinstance(text, bytes):
                target.write_bytes(text)
            else:
                target.write_text(text, encoding="utf-8")
            loaded = asdict(load_preferences(target))
            case = {"name": name, "prefs": loaded}
            if isinstance(text, bytes):
                case["hex"] = text.hex()
            else:
                case["raw"] = text
            cases.append(case)

        saves = []
        variants = [
            {},
            {"camera_id": None},
            {"camera_id": 3, "camera_brightness": 5.0, "audio_gain": 10.0},
            {"camera_brightness": -100.0, "camera_contrast": 0.5, "shot_threshold": 0.01},
            {"audio_device": 'quote " back \\ tab \t nl \n \u00e9 \u20ac \U0001f3a4 \x7f \x01'},
            {"target_face": "", "show_hold_zone": False, "invert_trace_vertical": True},
            {"audio_gain": 1e-5, "shot_threshold": 0.0001, "circle_diameter_mm": 1e16},
            {"audio_gain": 123456789012345680.0, "shot_diameter_mm": 5e-324},
            {"camera_brightness": -0.0, "tracking_region_fraction": 0.1 + 0.2},
            {"shot_refractory_ms": -5, "pre_shot_ms": 2147483647},
        ]
        for fields in variants:
            prefs = Preferences(**fields)
            save_preferences(prefs, target)
            saves.append({"prefs": asdict(prefs), "text": target.read_text()})

    data_dirs = []
    home = Path("/home/user")
    envs = [
        {},
        {"APPDATA": "/appdata", "XDG_DATA_HOME": "/xdg"},
        {"APPDATA": "", "XDG_DATA_HOME": ""},
        {"APPDATA": "/data with space", "XDG_DATA_HOME": "/data with space"},
        {"HOME": "/ignored"},
    ]
    for platform in ("win32", "darwin", "linux"):
        for env in envs:
            with (
                mock.patch.object(paths.sys, "platform", platform),
                mock.patch.dict(os.environ, env, clear=True),
                mock.patch.object(Path, "home", return_value=home),
                mock.patch.object(Path, "mkdir"),
            ):
                result = paths.data_dir()
            data_dirs.append(
                {
                    "platform": {"win32": "windows", "darwin": "macos", "linux": "linux"}[platform],
                    "env": env,
                    "home": str(home),
                    "path": str(result),
                }
            )
    return {"defaults": defaults, "cases": cases, "saves": saves, "data_dirs": data_dirs}


def stores() -> dict:
    import logging
    from dataclasses import asdict

    from shottrainer.app.camera_selection import (
        CameraSelection,
        load_camera_selection,
        resolve_camera_index,
        save_camera_selection,
    )
    from shottrainer.app.detector_store import load_detector_settings, save_detector_settings
    from shottrainer.app.ui_state import UiState, load_ui_state, save_ui_state
    from shottrainer.app.zero_offset_store import load_zero_offset, save_zero_offset
    from shottrainer.tracking.detector import DetectorSettings

    def dumps(value: object) -> str:
        return json.dumps(value, allow_nan=True)

    class Warned(logging.Handler):
        """Records whether a loader logged a warning, which marks a rejected file."""

        def __init__(self) -> None:
            super().__init__(logging.WARNING)
            self.hit = False

        def emit(self, record: logging.LogRecord) -> None:
            self.hit = True

    def run(texts: list[tuple[str, str | bytes]], load, logger: str, convert) -> list[dict]:
        out = []
        handler = Warned()
        logging.getLogger(logger).addHandler(handler)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "state.json"
                for name, text in texts:
                    if isinstance(text, bytes):
                        target.write_bytes(text)
                    else:
                        target.write_text(text, encoding="utf-8")
                    handler.hit = False
                    value = load(target)
                    case = {"name": name, "expected": convert(value, handler.hit)}
                    case["hex" if isinstance(text, bytes) else "raw"] = (
                        text.hex() if isinstance(text, bytes) else text
                    )
                    out.append(case)
        finally:
            logging.getLogger(logger).removeHandler(handler)
        return out

    def saved_text(save, value, name: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / name
            save(value, target)
            return {"text": target.read_text() if target.exists() else None}

    common: list[tuple[str, str | bytes]] = [
        ("empty object", "{}"),
        ("null", "null"),
        ("array", "[]"),
        ("number", "3"),
        ("string", '"x"'),
        ("true", "true"),
        ("invalid json", "not json"),
        ("truncated", '{"x_mm": 1.5,'),
        ("empty file", ""),
        ("invalid utf-8", b"\xff\xfe"),
    ]

    # Detector settings. A rejected file loads as None.
    defaults = asdict(DetectorSettings())
    detector_texts = [
        *common,
        ("detector valid", dumps({**defaults, "min_radius_px": 8, "region_fraction": 0.5})),
        ("detector unknown keys", '{"min_radius_px": 12, "totally_unknown": 99}'),
        ("detector truncated", '{"min_radius_px": 12, "max_ra'),
        ("detector integers for floats", '{"lock_radius_px": 80, "lock_boost": 2}'),
        ("detector float 17 digits", '{"min_circularity": 0.19862074538694519}'),
        ("detector int32 max", '{"max_candidates": 2147483647}'),
        ("detector int past int32", '{"max_candidates": 2147483648}'),
        ("detector huge float", '{"lock_radius_px": 1e999}'),
    ]
    for key, values in {
        "min_radius_px": [0, 1, -1, 201, 200, "4", 4.0, None, True],
        "max_radius_px": [3, 4, 5, 0, [], "x"],
        "blur_kernel": [0, 1, 2, 3, 4, 7, -1, "5", 3.5, True, None],
        "min_circularity": [0, 1, 1.0, 0.0, 1.01, -0.01, "0.5", True, None, float("nan")],
        "adaptive_block_size": [2, 3, 4, 31, 3.5, "31", True],
        "adaptive_offset": [-5, 0, 5, 5.5, "5", None, False],
        "region_fraction": [0, 0.01, 1, 1.0, 1.01, 2.0, -1, None, float("inf"), "0.7"],
        "lock_radius_px": [0, 0.5, -1, 1e300, float("-inf"), True, None, "80"],
        "lock_boost": [0, 0.1, -0.5, 100, True, None],
        "lock_release_after_misses": [0, 1, -1, 8.0, True, None],
        "opening_kernel_px": [-1, 0, 1, 2, 3, "3", 3.0],
        "closing_kernel_px": [-1, 0, 4, None],
        "max_candidates": [0, 1, -1, True, None, "200"],
        "lock_search_radius_factor": [0, 0.1, -2, float("nan"), "2.0", True],
    }.items():
        for value in values:
            detector_texts.append((f"detector {key} {value!r}", dumps({key: value})))
    detector_texts.append(("detector min above max", dumps({"min_radius_px": 201})))
    detector_texts.append(
        ("detector min equals max", dumps({"min_radius_px": 9, "max_radius_px": 9}))
    )

    detector_saves = [
        DetectorSettings(),
        DetectorSettings(min_radius_px=8, max_radius_px=300, blur_kernel=7, region_fraction=0.5),
        DetectorSettings(min_circularity=0.1 + 0.2, lock_radius_px=1e16, lock_boost=1e-5),
    ]

    # Zero offset. A rejected file loads as (0, 0), told apart by the warning.
    zero_texts = [
        *common,
        ("zero valid", dumps({"x_mm": 1.5, "y_mm": -2.25})),
        ("zero unknown keys", '{"x_mm": 1, "y_mm": 2, "z": 3}'),
        ("zero integers", '{"x_mm": 3, "y_mm": -4}'),
        ("zero explicit zeros", '{"x_mm": 0, "y_mm": 0}'),
        ("zero negative zero float", '{"x_mm": -0.0, "y_mm": 0.0}'),
        ("zero negative zero int", '{"x_mm": -0, "y_mm": 1}'),
        ("zero missing y", '{"x_mm": 1}'),
        ("zero missing x", '{"y_mm": 1}'),
        ("zero 17 digit float", '{"x_mm": 0.19862074538694519, "y_mm": 1}'),
        ("zero largest finite", dumps({"x_mm": 1.7976931348623157e308, "y_mm": 1})),
        ("zero numeric strings", '{"x_mm": "2.5", "y_mm": " -1_0.5e1 "}'),
        ("zero bad strings", '{"x_mm": "abc", "y_mm": 1}'),
        ("zero empty string", '{"x_mm": "", "y_mm": 1}'),
        ("zero underscore at end", '{"x_mm": "1_", "y_mm": 1}'),
        ("zero double underscore", '{"x_mm": "1__0", "y_mm": 1}'),
        ("zero dot only", '{"x_mm": ".", "y_mm": 1}'),
        ("zero leading dot", '{"x_mm": ".5", "y_mm": 1}'),
        ("zero trailing dot", '{"x_mm": "5.", "y_mm": 1}'),
        ("zero overflow string", '{"x_mm": "1e999", "y_mm": 1}'),
        ("zero nan string", '{"x_mm": "nan", "y_mm": 1}'),
        ("zero inf string", '{"x_mm": "-inf", "y_mm": 1}'),
        ("zero not json number", '{"x_mm": 1.5.5, "y_mm": 1}'),
    ]
    for axis in ("x_mm", "y_mm"):
        other = "y_mm" if axis == "x_mm" else "x_mm"
        for label, value in [
            ("nan", float("nan")),
            ("infinity", float("inf")),
            ("negative infinity", float("-inf")),
        ]:
            zero_texts.append((f"zero {axis} {label}", dumps({axis: value, other: 2.5})))
        for label, literal in [
            ("exponent", "1e999"),
            ("negative exponent", "-1e999"),
            ("huge int", "9" * 400),
            ("bool", "true"),
            ("null", "null"),
            ("list", "[]"),
            ("object", "{}"),
        ]:
            zero_texts.append((f"zero {axis} {label}", f'{{"{axis}": {literal}, "{other}": 2.5}}'))

    zero_saves = [
        (1.5, -2.25),
        (1e-5, 1e16),
        (-0.0, 0.5),
        (0.1 + 0.2, -3.0),
        (0.0, 0.0),
        (-0.0, 0.0),
    ]

    # Camera selection. The Python loader raises on a document that is not an
    # object, so those cases are left to the Rust fallback tests.
    camera_texts = [
        ("camera empty object", "{}"),
        ("camera truncated", '{"name": "USB'),
        ("camera empty file", ""),
        ("camera invalid json", "not json"),
        ("camera valid", '{"name": "USB Cam", "index": 2}'),
        ("camera unicode", '{"name": "Cam \\u00e9 \\ud83c\\udfa4", "index": 1}'),
        ("camera unknown keys", '{"name": "A", "index": 3, "extra": [1]}'),
        ("camera index null", '{"name": "A", "index": null}'),
        ("camera missing index", '{"name": "A"}'),
        ("camera missing name", '{"index": 4}'),
        ("camera negative index", '{"name": "A", "index": -1}'),
        ("camera index true", '{"name": "A", "index": true}'),
        ("camera index false", '{"name": "A", "index": false}'),
        ("camera index float", '{"name": "A", "index": 1.0}'),
        ("camera index string", '{"name": "A", "index": "1"}'),
        ("camera index list", '{"name": "A", "index": [1]}'),
        ("camera index big", '{"name": "A", "index": 9007199254740993}'),
        ("camera name null", '{"name": null, "index": 1}'),
        ("camera name int", '{"name": 5, "index": 1}'),
        ("camera name float", '{"name": 2.50, "index": 1}'),
        ("camera name true", '{"name": true, "index": 1}'),
        ("camera name false", '{"name": false}'),
        ("camera name list", '{"name": [1, "a", null, true, 1.5, {"k": []}]}'),
        ("camera name object", '{"name": {"it\'s": "x", "b": "say \\"hi\\"", "c": "both \' \\""}}'),
        ("camera name escapes", '{"name": ["tab\\t nl\\n back\\\\ \\u0001 \\u007f \\u00e9"]}'),
    ]
    camera_saves = [
        CameraSelection(),
        CameraSelection(name="USB Cam", index=2),
        CameraSelection(name="", index=None),
        CameraSelection(name='quote " back \\ tab \t \u00e9 \U0001f3a4 \x7f', index=-3),
    ]
    available_sets = [
        [],
        [(0, "Built-in"), (3, "USB Cam")],
        [(0, "Built-in"), (2, "USB Cam")],
        [(1, "Built-in")],
        [(5, "Same"), (6, "Same")],
    ]
    selections = [
        CameraSelection(name="USB Cam", index=99),
        CameraSelection(name="Unknown", index=2),
        CameraSelection(name="Unknown", index=99),
        CameraSelection(name="Anything", index=5),
        CameraSelection(name="", index=None),
        CameraSelection(name="Same", index=6),
        CameraSelection(),
    ]
    resolves = [
        {
            "name": sel.name,
            "index": sel.index,
            "available": [list(a) for a in avail],
            "result": resolve_camera_index(sel, avail),
        }
        for sel in selections
        for avail in available_sets
    ]

    # Window state.
    ui_texts = [
        *common,
        ("ui valid", '{"window_geometry_b64": "QmFzZTY0", "main_splitter_sizes": [200, 400]}'),
        ("ui unknown keys", '{"window_geometry_b64": "x", "main_splitter_sizes": [1], "k": 1}'),
        ("ui missing geometry", '{"main_splitter_sizes": [5]}'),
        ("ui missing sizes", '{"window_geometry_b64": "abc"}'),
        ("ui geometry not base64", '{"window_geometry_b64": "not base64 ###"}'),
        ("ui geometry number", '{"window_geometry_b64": 5, "main_splitter_sizes": [1]}'),
        ("ui geometry null", '{"window_geometry_b64": null}'),
        ("ui sizes not list", '{"window_geometry_b64": "a", "main_splitter_sizes": "1,2"}'),
        ("ui sizes object", '{"main_splitter_sizes": {"a": 1}}'),
        (
            "ui mixed sizes",
            dumps(
                {
                    "window_geometry_b64": "QmFzZTY0",
                    "main_splitter_sizes": [
                        200,
                        "400",
                        "--1",
                        "\u00b2",
                        -1,
                        True,
                        None,
                        2.5,
                        2**40,
                        0,
                    ],
                }
            ),
        ),
        (
            "ui string sizes",
            '{"main_splitter_sizes": [" 7 ", "+8", "1_000", "1__0", "_1", "1_", "", " ", "0x10", "1e2", "-0", "-1", "2147483647", "2147483648", "9'
            + "9" * 40
            + '", "\\u00a05\\u00a0", "\\n6\\n"]}',
        ),
        (
            "ui int bounds",
            '{"main_splitter_sizes": [2147483647, 2147483648, -2147483648, 0, -0, 1e2, 1.0, 100000000000000000000]}',
        ),
        ("ui nan sizes", '{"main_splitter_sizes": [NaN, 1, Infinity, -Infinity, 1e999, 2]}'),
        ("ui nested sizes", '{"main_splitter_sizes": [[1], {"a": 1}, false, 3]}'),
        ("ui empty strings", '{"window_geometry_b64": "", "main_splitter_sizes": []}'),
        ("ui unicode geometry", r'{"window_geometry_b64": "\u00e9 \ud83c\udfa4"}'),
    ]
    ui_saves = [
        UiState(),
        UiState(window_geometry_b64="QmFzZTY0", main_splitter_sizes=[200, 400]),
        UiState(
            window_geometry_b64='q " \\ \n \u00e9 \U0001f3a4 \x7f',
            main_splitter_sizes=[0, 2147483647],
        ),
    ]

    def convert_detector(value, _warned):
        return None if value is None else asdict(value)

    def convert_zero(value, warned):
        return None if warned else list(value)

    return {
        "detector_defaults": defaults,
        "detector": run(
            detector_texts,
            load_detector_settings,
            "shottrainer.app.detector_store",
            convert_detector,
        ),
        "detector_saves": [
            {"value": asdict(v), **saved_text(save_detector_settings, v, "d.json")}
            for v in detector_saves
        ],
        "zero": run(
            zero_texts, load_zero_offset, "shottrainer.app.zero_offset_store", convert_zero
        ),
        "zero_saves": [
            {
                "value": [encode_number(a), encode_number(b)],
                **saved_text(save_zero_offset, (a, b), "z.json"),
            }
            for a, b in zero_saves
        ],
        "camera": run(
            camera_texts,
            load_camera_selection,
            "shottrainer.app.camera_selection",
            lambda v, _w: asdict(v),
        ),
        "camera_saves": [
            {"value": asdict(v), **saved_text(save_camera_selection, v, "c.json")}
            for v in camera_saves
        ],
        "resolve": resolves,
        "ui": run(ui_texts, load_ui_state, "shottrainer.app.ui_state", lambda v, _w: asdict(v)),
        "ui_saves": [
            {"value": asdict(v), **saved_text(save_ui_state, v, "u.json")} for v in ui_saves
        ],
    }


def target_faces() -> dict:
    import shottrainer.app.target_faces as tf

    def face_dict(face: object) -> dict:
        return {
            "key": face.key,
            "label": face.label,
            "rings": [[r.diameter_mm, r.label] for r in face.rings],
            "shot_diameter_mm": face.shot_diameter_mm,
            "face_diameter_mm": face.face_diameter_mm,
            "scoring_direction": face.scoring_direction,
        }

    ring = {"diameter_mm": 10.0, "label": "X"}
    texts: list[tuple[str, str | bytes | None]] = [
        ("missing", None),
        ("empty_object", "{}"),
        ("empty_list", "[]"),
        ("list_top_level", '[{"rings": [{"diameter_mm": 5}]}]'),
        ("string_top_level", '"faces"'),
        ("number_top_level", "7"),
        ("garbage", "not json"),
        ("invalid_utf8", b"\xff\xfe"),
        ("truncated", '{"a": {"rings": [{"diameter_mm": 5}'),
        (
            "valid",
            json.dumps(
                {
                    "my_face": {
                        "label": "My face",
                        "shot_diameter_mm": 5.6,
                        "face_diameter_mm": 112.5,
                        "scoring_direction": "outward",
                        "rings": [{"diameter_mm": 100.0, "label": "1"}, ring],
                    },
                    "plain": {"rings": [{"diameter_mm": 3}]},
                }
            ),
        ),
        ("unknown_keys", json.dumps({"u": {"rings": [ring], "colour": "red", "extra": [1]}})),
        (
            "body_not_object",
            json.dumps({"a": [1], "b": "x", "c": None, "d": 3, "e": {"rings": [ring]}}),
        ),
        ("missing_rings", json.dumps({"a": {"label": "No rings"}, "b": {"rings": [ring]}})),
        ("rings_not_list", json.dumps({"a": {"rings": {"diameter_mm": 5}}, "b": {"rings": "x"}})),
        ("rings_empty", json.dumps({"a": {"rings": []}})),
        (
            "ring_entries",
            json.dumps({"a": {"rings": [1, "x", None, [], {"label": "no diameter"}, ring]}}),
        ),
        (
            "ring_diameters",
            json.dumps(
                {
                    "a": {
                        "rings": [
                            {"diameter_mm": 0, "label": "zero"},
                            {"diameter_mm": -1.5, "label": "neg"},
                            {"diameter_mm": True, "label": "bool"},
                            {"diameter_mm": None, "label": "null"},
                            {"diameter_mm": "12.5", "label": "str"},
                            {"diameter_mm": " 1_0 ", "label": "under"},
                            {"diameter_mm": "abc", "label": "text"},
                            {"diameter_mm": "inf", "label": "infstr"},
                            {"diameter_mm": [3], "label": "list"},
                            {"diameter_mm": 10**400, "label": "huge"},
                            {"diameter_mm": 2, "label": "int"},
                            {"diameter_mm": 1e-300, "label": "tiny"},
                        ]
                    }
                }
            ),
        ),
        (
            "non_finite_tokens",
            '{"a": {"rings": [{"diameter_mm": NaN}, {"diameter_mm": Infinity},'
            ' {"diameter_mm": -Infinity}, {"diameter_mm": 1e999}, {"diameter_mm": 4}],'
            ' "shot_diameter_mm": NaN, "face_diameter_mm": Infinity}}',
        ),
        (
            "metadata",
            json.dumps(
                {
                    "a": {"rings": [ring], "shot_diameter_mm": "huge", "face_diameter_mm": -1},
                    "b": {"rings": [ring], "shot_diameter_mm": "5.6", "face_diameter_mm": 0},
                    "c": {"rings": [ring], "shot_diameter_mm": True, "face_diameter_mm": 10**400},
                    "d": {"rings": [ring], "shot_diameter_mm": 4, "face_diameter_mm": [1]},
                }
            ),
        ),
        (
            "labels",
            json.dumps(
                {
                    "n": {"label": 5, "rings": [{"diameter_mm": 1, "label": 9}]},
                    "z": {"label": 0, "rings": [{"diameter_mm": 1, "label": 0.0}]},
                    "f": {"label": 2.5, "rings": [{"diameter_mm": 1, "label": False}]},
                    "t": {"label": True, "rings": [{"diameter_mm": 1, "label": True}]},
                    "l": {"label": [1, "a"], "rings": [{"diameter_mm": 1, "label": [1.0, None]}]},
                    "o": {"label": {"a": 1}, "rings": [{"diameter_mm": 1, "label": {}}]},
                    "s": {"label": "", "rings": [{"diameter_mm": 1, "label": None}]},
                    "u": {"label": "caf\u00e9 \u2603", "rings": [{"diameter_mm": 1, "label": "X"}]},
                }
            ),
        ),
        (
            "directions",
            json.dumps(
                {
                    "a": {"scoring_direction": "outward", "rings": [ring]},
                    "b": {"scoring_direction": "sideways", "rings": [ring]},
                    "c": {"scoring_direction": "Outward", "rings": [ring]},
                    "d": {"scoring_direction": 1, "rings": [ring]},
                    "e": {"scoring_direction": None, "rings": [ring]},
                    "f": {"scoring_direction": ["inward"], "rings": [ring]},
                }
            ),
        ),
        (
            "duplicate_ids",
            '{"d": {"label": "first", "rings": [{"diameter_mm": 1}]},'
            ' "e": {"rings": [{"diameter_mm": 2}]},'
            ' "d": {"label": "second", "rings": [{"diameter_mm": 3}]}}',
        ),
        (
            "built_in_collision",
            json.dumps(
                {
                    "default": {"label": "Mine", "rings": [{"diameter_mm": 99, "label": "1"}]},
                    "smallbore_50m": {"rings": [{"diameter_mm": -10}]},
                    "air_rifle_10m": {"label": "aaa first", "rings": [ring]},
                }
            ),
        ),
        (
            "sorting",
            json.dumps(
                {
                    "z": {"label": "Zed", "rings": [ring]},
                    "b": {"label": "alpha", "rings": [ring]},
                    "c": {"label": "Alpha", "rings": [ring]},
                    "d": {"label": "\u00c9clair", "rings": [ring]},
                    "e": {"label": "\u03a3\u03a3", "rings": [ring]},
                }
            ),
        ),
    ]

    cases = []
    original = tf.custom_faces_path
    try:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "custom_target_faces.json"
            tf.custom_faces_path = lambda: target
            for name, text in texts:
                target.unlink(missing_ok=True)
                if isinstance(text, bytes):
                    target.write_bytes(text)
                elif text is not None:
                    target.write_text(text, encoding="utf-8")
                tf.reload_custom_faces()
                custom = list(tf._load_custom_faces().values())
                case = {
                    "name": name,
                    "faces": [face_dict(f) for f in custom],
                    "list": tf.list_target_faces(),
                    "merged_keys": list(tf._merged_faces()),
                    "fallback": tf.get_face("nonsense").key,
                }
                if isinstance(text, bytes):
                    case["bytes_hex"] = text.hex()
                else:
                    case["text"] = text
                cases.append(case)
            # A directory in place of the file is unreadable.
            target.unlink(missing_ok=True)
            target.mkdir()
            tf.reload_custom_faces()
            cases.append(
                {
                    "name": "directory",
                    "directory": True,
                    "faces": [],
                    "list": tf.list_target_faces(),
                    "merged_keys": list(tf._merged_faces()),
                    "fallback": tf.get_face("nonsense").key,
                }
            )
    finally:
        tf.custom_faces_path = original
        tf.reload_custom_faces()

    built_in = [face_dict(f) for f in tf._load_built_in_faces().values()]
    return {"built_in": built_in, "cases": cases}


AREAS = {
    "preferences": preferences,
    "scoring": scoring,
    "shot_stats": shot_stats,
    "trace": trace,
    "export_csv": export_csv,
    "stores": stores,
    "target_faces": target_faces,
}

if __name__ == "__main__":
    name = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    data = AREAS[name]()
    if name == "export_csv":
        # One entry per line keeps the fixture compact.
        text = (
            "{\n"
            + ",\n".join(
                f"{json.dumps(k)}:{json.dumps(v, separators=(',', ':'))}"
                if k == "files"
                else f"{json.dumps(k)}:[\n"
                + ",\n".join(json.dumps(i, separators=(",", ":")) for i in v)
                + "\n]"
                for k, v in data.items()
            )
            + "\n}\n"
        )
    elif name in ("preferences", "stores", "target_faces"):

        def compact(v: object) -> str:
            return json.dumps(v, separators=(",", ":"))

        text = (
            "{\n"
            + ",\n".join(
                f"{json.dumps(k)}:{compact(v)}"
                if not isinstance(v, list)
                else f"{json.dumps(k)}:[\n" + ",\n".join(compact(i) for i in v) + "\n]"
                for k, v in data.items()
            )
            + "\n}\n"
        )
    else:
        text = json.dumps(data, indent=1) + "\n"
    (OUT / f"{name}.json").write_text(text)
    print(f"wrote {name}")
