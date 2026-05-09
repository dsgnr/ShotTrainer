"""SQLAlchemy models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA_VERSION = 3

# Allowed values for ``Session.category``. The strings are stored
# verbatim in the database so they need to stay stable across versions.
SESSION_CATEGORIES: tuple[str, ...] = ("practice", "sighter", "match")
DEFAULT_SESSION_CATEGORY = "practice"


def utc_now() -> datetime:
    """Naive UTC ``datetime`` for column defaults.

    The columns are tz-naive ``DateTime`` because SQLite has no
    native tz-aware type. ``datetime.utcnow`` is deprecated since
    Python 3.12, so this helper builds a tz-aware ``datetime``
    and strips the tzinfo to keep the on-disk shape unchanged.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


class SchemaMeta(Base):
    """Tracks the current schema version for migration decisions."""

    __tablename__ = "schema_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)


class Session(Base):
    """A single training session, from start to stop.

    Holds metadata (name, notes, target profile) and owns the
    related :class:`Shot` rows via a cascade relationship. Trace
    samples live in their own table for bulk-insert performance.
    """

    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_profile: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    category: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DEFAULT_SESSION_CATEGORY
    )
    app_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=SCHEMA_VERSION)

    shots: Mapped[list[Shot]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class TraceSample(Base):
    """One tracking sample persisted to the database.

    ``ts`` is the monotonic timestamp from the camera loop. Pixel
    coordinates are always present. Millimetre coordinates are
    ``None`` when the tracker couldn't convert (no circle found).
    """

    __tablename__ = "trace_samples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[float] = mapped_column(Float, nullable=False)  # monotonic seconds
    x_px: Mapped[float] = mapped_column(Float, nullable=False)
    y_px: Mapped[float] = mapped_column(Float, nullable=False)
    x_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    y_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    frame_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


Index("ix_trace_session_ts", TraceSample.session_id, TraceSample.ts)


class Shot(Base):
    """A single shot detected during a session.

    ``x_mm`` / ``y_mm`` are the aim coordinates at the moment of
    the shot. ``None`` when the tracker didn't have a lock at that
    instant. ``score`` holds the ring label assigned by the
    scoring service, or an empty string when unscored.
    """

    __tablename__ = "shots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ts: Mapped[float] = mapped_column(Float, nullable=False)
    x_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    y_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score: Mapped[str] = mapped_column(String(16), nullable=False, default="")

    session: Mapped[Session] = relationship(back_populates="shots")
