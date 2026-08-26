"""Database engine."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shottrainer import __version__

from .models import SCHEMA_VERSION, Base, SchemaMeta

log = logging.getLogger(__name__)


def make_engine(db_path: str | Path) -> Engine:
    """Build a SQLAlchemy engine that points at ``db_path``.

    Pass ``":memory:"`` to use an in-memory database.

    ``check_same_thread=False`` lets the engine be reused across
    threads when needed. SQLAlchemy still hands out one connection
    per thread from its pool, so SQLite-level transactions remain
    serialised.

    For ``:memory:`` we additionally swap to ``StaticPool`` so every
    connection sees the same in-memory database. Without that, each
    new connection from the default pool gets its own empty database
    and rows written through one connection are invisible to the next.
    """
    is_memory = str(db_path) == ":memory:"
    url = "sqlite:///:memory:" if is_memory else f"sqlite:///{db_path}"
    kwargs: dict[str, object] = {
        "future": True,
        "connect_args": {"check_same_thread": False},
    }
    if is_memory:
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Turn on ``PRAGMA foreign_keys=ON`` for every fresh connection.

    SQLite leaves foreign keys off by default. Without this, the
    ``ON DELETE CASCADE`` declarations on the trace and shot
    tables wouldn't fire when a session is deleted.
    """

    @event.listens_for(engine, "connect")
    def _fk_pragma_on_connect(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def make_session_factory(engine: Engine) -> sessionmaker[OrmSession]:
    """Return a configured ``sessionmaker`` bound to ``engine``."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_database(engine: Engine) -> None:
    """Create any missing tables and run pending migrations.

    The schema version sits in ``schema_meta``. If the row's
    version is older than :data:`SCHEMA_VERSION` we call
    :func:`migrate` with the current version so it can patch the
    schema in place.
    """
    Base.metadata.create_all(engine)
    with OrmSession(engine, future=True) as session:
        existing = session.execute(select(SchemaMeta).limit(1)).scalar_one_or_none()
        if existing is None:
            session.add(SchemaMeta(version=SCHEMA_VERSION, app_version=__version__))
            session.commit()
            return
        if existing.version != SCHEMA_VERSION:
            migrate(engine, from_version=existing.version)
            existing.version = SCHEMA_VERSION
            existing.app_version = __version__
            session.commit()


def migrate(engine: Engine, from_version: int) -> None:
    """Apply schema changes from ``from_version`` up to the latest.

    Each step is a small block guarded by the version it upgrades
    *from*, so a database that's several versions behind walks
    through them in order without having to know the full history.
    """
    if from_version < 2:
        _drop_legacy_calibration_column(engine)
    if from_version < 3:
        _add_session_category_column(engine)


def _drop_legacy_calibration_column(engine: Engine) -> None:
    """Remove the unused ``sessions.calibration_json`` column from a v1 database.

    The calibration step was retired when the live circle tracker
    landed. The column has been unused since then, but kept
    around to avoid touching the schema. Now that there's a
    migration path (schema v2) the column can be dropped cleanly.
    SQLite supports ``ALTER TABLE ... DROP COLUMN`` from 3.35.
    Python 3.13 ships a newer SQLite, so the statement is safe.
    """
    with engine.begin() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)")}
        if "calibration_json" in existing:
            conn.execute(text("ALTER TABLE sessions DROP COLUMN calibration_json"))
            log.info("Dropped legacy column sessions.calibration_json")


def _add_session_category_column(engine: Engine) -> None:
    """Add the ``sessions.category`` column to a v2 database.

    Existing rows default to ``"practice"`` so the browser can show
    them with a category badge straight away. Future writes go
    through the ORM column default.
    """
    with engine.begin() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)")}
        if "category" not in existing:
            conn.execute(
                text(
                    "ALTER TABLE sessions ADD COLUMN category VARCHAR(16) "
                    "NOT NULL DEFAULT 'practice'"
                )
            )
            log.info("Added column sessions.category")
