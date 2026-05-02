"""Tests for the session browser dialog.

Covers the deferred-load path so the dialog appears immediately
with a "Loading..." placeholder and the rows arrive on the next
event loop tick.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.ui.session_browser import SessionBrowserDialog


@pytest.fixture()
def repo() -> SessionRepository:
    """A fresh in-memory repository, isolated per test."""
    engine = make_engine(":memory:")
    init_database(engine)
    return SessionRepository(engine)


def test_dialog_shows_empty_state_when_no_sessions(qtbot, repo: SessionRepository):
    """A repository with no sessions should land on the empty-state page."""
    dialog = SessionBrowserDialog(repo)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    qtbot.waitUntil(
        lambda: dialog._stack.currentWidget() is dialog._empty,
        timeout=2000,
    )
    assert dialog._list.count() == 0
    assert not dialog._open.isEnabled()


def test_dialog_starts_on_loading_page(qtbot, repo: SessionRepository):
    """The dialog should appear with the loading placeholder before
    the deferred query has had a chance to run, so users see the
    window immediately even on a slow database."""
    repo.create_session(name="evening practice")

    dialog = SessionBrowserDialog(repo)
    qtbot.addWidget(dialog)

    # Right after construction, before the event loop has had a
    # chance to fire the deferred populate, the loading page is
    # active.
    assert dialog._stack.currentWidget() is dialog._loading


def test_dialog_loads_sessions(qtbot, repo: SessionRepository):
    """Sessions appear in the list once the deferred load runs."""
    repo.create_session(name="evening practice")
    repo.create_session(name="club night")

    dialog = SessionBrowserDialog(repo)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    qtbot.waitUntil(lambda: dialog._list.count() == 2, timeout=2000)
    assert dialog._stack.currentWidget() is dialog._list


def test_back_to_back_refresh_keeps_only_the_latest(qtbot, repo: SessionRepository):
    """A refresh issued while one is pending invalidates the older one."""
    repo.create_session(name="sighters")
    dialog = SessionBrowserDialog(repo)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    dialog.refresh()
    dialog.refresh()
    dialog.refresh()

    qtbot.waitUntil(lambda: dialog._list.count() == 1, timeout=2000)
