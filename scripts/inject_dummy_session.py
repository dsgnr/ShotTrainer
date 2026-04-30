"""Populate the database with a handful of realistic demo sessions.

Run with:
    uv run python scripts/inject_dummy_session.py

This creates several NSRA 25-yard prone rifle sessions on different
dates, each with slightly different shooting performance and hold
quality.

Useful when you want a database that already contains believable
history for browsing sessions, viewing traces, testing statistics,
or taking screenshots.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as OrmSession

from shottrainer.app.paths import database_path
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.models import Session
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.models import TrackingSample

# NSRA 25-yard prone rifle target.
# Rings are listed from the centre outwards.
NSRA_25YD_RINGS = [
    (6.5, "10"),
    (10.0, "9"),
    (13.75, "8"),
    (17.25, "7"),
    (20.75, "6"),
]

SHOT_DIAMETER_MM = 5.6  # .22LR

# Settings that control how much tracking data is generated
# around each shot and how smooth the traces appear.
TRACE_FPS = 120
PRE_SHOT_WINDOW_S = 5.0
POST_SHOT_WINDOW_S = 1.0
SETTLE_TIME_S = 3.5
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080
TRACKING_CIRCLE_MM = 51.5


def score_shot_nsra_25yd(x_mm: float, y_mm: float) -> str:
    """Return the score for a shot on the NSRA 25-yard target."""
    distance = math.sqrt(x_mm**2 + y_mm**2)
    shot_edge = distance - SHOT_DIAMETER_MM / 2

    for radius, label in NSRA_25YD_RINGS:
        if shot_edge < radius:
            return label

    return ""


def generate_trace(
    start_ts: float,
    duration_s: float,
    centre_x: float,
    centre_y: float,
    tremor_mm: float = 1.5,
    walk_from: tuple[float, float] | None = None,
) -> list[TrackingSample]:
    """Generate tracking data that resembles a real aiming trace.

    Most traces start with the rifle moving onto the target and then
    settling into the aim point before the shot breaks. Small amounts
    of movement are added to mimic breathing and natural hold wobble.
    """
    samples = []
    n = int(duration_s * TRACE_FPS)

    if walk_from is None:
        # Simulate a steady hold around the aim point.
        x, y = centre_x, centre_y

        for i in range(n):
            t = start_ts + i / TRACE_FPS

            x += random.gauss(0, tremor_mm * 0.10) + (centre_x - x) * 0.04
            y += random.gauss(0, tremor_mm * 0.10) + (centre_y - y) * 0.04

            breath = 1.5 * math.sin(2 * math.pi * 0.2 * (i / TRACE_FPS))
            mm_per_px = TRACKING_CIRCLE_MM / 180

            samples.append(
                TrackingSample(
                    timestamp=t,
                    x_px=FRAME_WIDTH / 2 + x / mm_per_px,
                    y_px=FRAME_HEIGHT / 2 + (y + breath) / mm_per_px,
                    x_mm=x,
                    y_mm=y + breath,
                    confidence=random.uniform(0.92, 1.0),
                    frame_id=i,
                )
            )

        return samples

    sx, sy = walk_from
    approach_frames = int(n * 0.75)

    # Create a natural-looking path onto the target rather than moving
    # in a perfectly straight line.
    dx = centre_x - sx
    dy = centre_y - sy

    perp_x = -dy
    perp_y = dx

    perp_len = math.sqrt(perp_x * perp_x + perp_y * perp_y) or 1.0
    perp_x /= perp_len
    perp_y /= perp_len

    bend = random.uniform(-25, 25)

    cx = (sx + centre_x) / 2 + perp_x * bend
    cy = (sy + centre_y) / 2 + perp_y * bend

    # Slow movement while bringing the rifle into position.
    wob_freq_x = random.uniform(0.6, 1.2)
    wob_freq_y = random.uniform(0.5, 1.0)
    wob_phase_x = random.uniform(0, 2 * math.pi)
    wob_phase_y = random.uniform(0, 2 * math.pi)

    # Small random movement carried through the trace.
    tremor_x = 0.0
    tremor_y = 0.0

    for i in range(n):
        t = start_ts + i / TRACE_FPS
        time_s = i / TRACE_FPS

        if i < approach_frames:
            p = i / approach_frames
            ease = p * p
            inv = 1.0 - ease

            x = inv * inv * sx + 2 * inv * ease * cx + ease * ease * centre_x
            y = inv * inv * sy + 2 * inv * ease * cy + ease * ease * centre_y

            # Add a little slow movement so the approach doesn't look mechanical.
            wobble_amp = 1.5 * (1.0 - ease * 0.5)

            x += wobble_amp * math.sin(2 * math.pi * wob_freq_x * time_s + wob_phase_x)
            y += wobble_amp * math.sin(2 * math.pi * wob_freq_y * time_s + wob_phase_y)

            tremor_x = 0.95 * tremor_x + 0.05 * random.gauss(0, tremor_mm * 1.5)
            tremor_y = 0.95 * tremor_y + 0.05 * random.gauss(0, tremor_mm * 1.5)

            x += tremor_x
            y += tremor_y
        else:
            # Gentle hand movement while settling into position.
            tremor_x = 0.92 * tremor_x + 0.08 * random.gauss(0, tremor_mm * 1.0)
            tremor_y = 0.92 * tremor_y + 0.08 * random.gauss(0, tremor_mm * 1.0)

            x += (centre_x - x) * 0.04 + tremor_x * 0.3
            y += (centre_y - y) * 0.04 + tremor_y * 0.3

        # Slightly larger breathing movement while approaching the target.
        breath_amp = 2.5 if i < approach_frames else 1.5
        breath = breath_amp * math.sin(2 * math.pi * 0.2 * time_s)

        mm_per_px = TRACKING_CIRCLE_MM / 180

        samples.append(
            TrackingSample(
                timestamp=t,
                x_px=FRAME_WIDTH / 2 + x / mm_per_px,
                y_px=FRAME_HEIGHT / 2 + (y + breath) / mm_per_px,
                x_mm=x,
                y_mm=y + breath,
                confidence=random.uniform(0.92, 1.0),
                frame_id=i,
            )
        )

    return samples


def create_session_with_date(
    engine,
    repo: SessionRepository,
    name: str,
    started_at: datetime,
    duration_minutes: float,
    num_shots: int,
    skill_spread_mm: float,
    tremor_range: tuple[float, float],
) -> None:
    """Create a demo session with a specific date and shooting profile."""

    # Create the session record first so we can attach shots and trace data.
    with OrmSession(engine, future=True) as orm:
        row = Session(
            name=name,
            started_at=started_at,
            target_profile="nsra_25yd_prone_rifle_2510_BM8918",
            app_version="0.0.0-demo",
        )
        orm.add(row)
        orm.commit()
        session_id = int(row.id)

    print(f"\nSession {session_id}: '{name}' ({started_at.strftime('%d %b %Y %H:%M')})")

    current_ts = 100.0
    all_trace: list[TrackingSample] = []

    for shot_num in range(num_shots):
        if shot_num > 0:
            # Give the shooter a moment to settle before the next shot.
            settle_trace = generate_trace(
                start_ts=current_ts,
                duration_s=SETTLE_TIME_S + random.uniform(-0.5, 1.0),
                centre_x=random.gauss(0, skill_spread_mm * 0.6),
                centre_y=random.gauss(0, skill_spread_mm * 0.6),
                tremor_mm=random.uniform(*tremor_range) * 1.3,
            )

            all_trace.extend(settle_trace)
            current_ts += SETTLE_TIME_S

        hold_centre_x = random.gauss(0, skill_spread_mm)
        hold_centre_y = random.gauss(0, skill_spread_mm)
        tremor = random.uniform(*tremor_range)

        # Start outside the scoring rings and move onto the target.
        approach_angle = random.uniform(0, 2 * math.pi)
        approach_dist = random.uniform(30, 45)

        approach_x = hold_centre_x + math.cos(approach_angle) * approach_dist
        approach_y = hold_centre_y + math.sin(approach_angle) * approach_dist

        pre_trace = generate_trace(
            start_ts=current_ts,
            duration_s=PRE_SHOT_WINDOW_S,
            centre_x=hold_centre_x,
            centre_y=hold_centre_y,
            tremor_mm=tremor,
            walk_from=(approach_x, approach_y),
        )

        all_trace.extend(pre_trace)
        current_ts += PRE_SHOT_WINDOW_S

        # Record the shot near the final hold position.
        shot_x = (pre_trace[-1].x_mm or 0.0) + random.gauss(0, 0.4)
        shot_y = (pre_trace[-1].y_mm or 0.0) + random.gauss(0, 0.4)

        shot_ts = current_ts
        score = score_shot_nsra_25yd(shot_x, shot_y)

        repo.add_shot(
            session_id,
            ts=shot_ts,
            x_mm=shot_x,
            y_mm=shot_y,
            audio_level=random.uniform(0.55, 0.90),
            confidence=random.uniform(0.91, 1.0),
            score=score,
        )

        print(f"  Shot {shot_num + 1:2d}: ({shot_x:+5.1f}, {shot_y:+5.1f}) mm = {score or 'miss'}")

        # Add a short section of trace after the shot.
        post_trace = generate_trace(
            start_ts=current_ts,
            duration_s=POST_SHOT_WINDOW_S,
            centre_x=shot_x + random.gauss(0, 0.6),
            centre_y=shot_y + random.gauss(0, 0.6),
            tremor_mm=random.uniform(*tremor_range) * 1.2,
        )

        all_trace.extend(post_trace)
        current_ts += POST_SHOT_WINDOW_S

    count = repo.append_trace(session_id, all_trace)
    print(f"  {count} trace samples")

    ended_at = started_at + timedelta(minutes=duration_minutes)
    repo.end_session(session_id, ended_at=ended_at)


def main() -> None:
    db_path = database_path()
    print(f"Database: {db_path}")

    engine = make_engine(db_path)
    init_database(engine)
    repo = SessionRepository(engine)

    # Remove any demo sessions from a previous run.
    with OrmSession(engine, future=True) as orm:
        old = (
            orm.execute(
                __import__("sqlalchemy").select(Session).where(Session.name.like("Demo session%"))
            )
            .scalars()
            .all()
        )

        for row in old:
            orm.delete(row)

        orm.commit()

        if old:
            print(f"Removed {len(old)} old demo session(s)")

    # A small mix of sessions spread across several weeks.
    base_date = datetime(2026, 5, 18, 18, 30, 0)

    sessions = [
        {
            "name": "Demo session - Evening practice",
            "date": base_date,
            "duration": 25,
            "shots": 10,
            "spread": 3.0,
            "tremor": (2.5, 4.0),
        },
        {
            "name": "Demo session - Quick sighters",
            "date": base_date + timedelta(days=2, hours=1),
            "duration": 10,
            "shots": 5,
            "spread": 4.0,
            "tremor": (3.0, 5.0),
        },
        {
            "name": "Demo session - Full card practice",
            "date": base_date + timedelta(days=5, hours=-0.5),
            "duration": 35,
            "shots": 20,
            "spread": 2.5,
            "tremor": (2.0, 3.5),
        },
        {
            "name": "Demo session - Morning session",
            "date": base_date + timedelta(days=9, hours=-8),
            "duration": 20,
            "shots": 10,
            "spread": 2.0,
            "tremor": (1.8, 3.0),
        },
        {
            "name": "Demo session - Club night",
            "date": base_date + timedelta(days=12, hours=0.5),
            "duration": 30,
            "shots": 15,
            "spread": 3.5,
            "tremor": (2.5, 4.5),
        },
        {
            "name": "Demo session - Steady session",
            "date": base_date + timedelta(days=16, hours=-1),
            "duration": 25,
            "shots": 10,
            "spread": 1.5,
            "tremor": (1.5, 2.5),
        },
    ]

    for s in sessions:
        create_session_with_date(
            engine=engine,
            repo=repo,
            name=s["name"],
            started_at=s["date"],
            duration_minutes=s["duration"],
            num_shots=s["shots"],
            skill_spread_mm=s["spread"],
            tremor_range=s["tremor"],
        )

    print("\nDone. All sessions injected.")


if __name__ == "__main__":
    random.seed(123)
    main()
