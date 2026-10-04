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


AREAS = {"scoring": scoring, "shot_stats": shot_stats}

if __name__ == "__main__":
    name = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(AREAS[name](), indent=1) + "\n")
    print(f"wrote {name}")
