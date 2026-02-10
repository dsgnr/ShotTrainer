"""Database engine setup and a tiny migration step.

Migrations are kept simple: on open, ensure tables exist and stamp the
schema version. When the schema changes, real migrations go in
``migrate``. For now there is only one version.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as SAS
from sqlalchemy.orm import sessionmaker

from shottrainer import __version__

from .models import SCHEMA_VERSION, Base, SchemaMeta

log = logging.getLogger(__name__)


def make_engine(db_path: str | Path) -> Engine:
    url = f"sqlite:///{db_path}" if str(db_path) != ":memory:" else "sqlite:///:memory:"
    engine = create_engine(url, future=True)
    _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _fk_pragma_on_connect(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def make_session_factory(engine: Engine) -> sessionmaker[SAS]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with SAS(engine, future=True) as session:
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
    """Placeholder for future schema migrations."""
    log.info("No migrations required (from %d)", from_version)
