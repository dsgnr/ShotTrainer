"""SQLAlchemy models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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

SCHEMA_VERSION = 1


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
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    calibration_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_profile: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    app_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=SCHEMA_VERSION)

    shots: Mapped[list[Shot]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class TraceSample(Base):
    __tablename__ = "trace_samples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
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


def to_dict(model: Any) -> dict[str, Any]:
    """Tiny helper for serialising a model row to a dict (debug, tests)."""
    return {c.key: getattr(model, c.key) for c in model.__table__.columns}
