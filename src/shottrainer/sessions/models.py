"""SQLAlchemy models and the schema version constant.

The schema is deliberately narrow. Trace samples live in their
own table so they can be inserted in batches and queried by
session without dragging the rest of the metadata in.
"""

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

SCHEMA_VERSION = 2


def utc_now() -> datetime:
    """Naive UTC ``datetime`` for column defaults.

    The columns are tz-naive ``DateTime`` because SQLite has no
    native tz-aware type. ``datetime.utcnow`` is deprecated since
    Python 3.12, so this helper builds a tz-aware ``datetime``
    and strips the tzinfo to keep the on-disk shape unchanged.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class SchemaMeta(Base):
    __tablename__ = "schema_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_profile: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    app_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=SCHEMA_VERSION)

    shots: Mapped[list[Shot]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class TraceSample(Base):
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
