"""Write golden fixtures from the Python implementation for the Rust tests."""

from __future__ import annotations

import json
import math
import sys
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


AREAS = {"scoring": scoring, "shot_stats": shot_stats, "trace": trace}

if __name__ == "__main__":
    name = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(AREAS[name](), indent=1) + "\n")
    print(f"wrote {name}")
