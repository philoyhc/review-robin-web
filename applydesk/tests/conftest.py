"""ApplyDesk's tests run signed in as the fake local super-admin, whatever
the developer's `.env` says; a test that needs someone else changes the
settings itself."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cordware.settings import identity_settings


@pytest.fixture(autouse=True)
def _fake_super_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "app_env", "local")
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    monkeypatch.setattr(identity_settings, "fake_auth_email", "admin@example.edu")
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", True)
    monkeypatch.setattr(identity_settings, "super_admin_emails", [])


@pytest.fixture(autouse=True)
def applydesk_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply Desk's database as a fresh SQLite file for every test, its
    tables made from the models (the migration is round-tripped in
    `test_applydesk_db.py`): the gate reads it (segment AD2A), so no test
    may reach a developer's `./applydesk.db`."""
    from applydesk import db, models

    monkeypatch.setenv("APPLYDESK_DATABASE_URL", f"sqlite:///{tmp_path / 'applydesk.db'}")
    db.engine.cache_clear()
    db._sessions.cache_clear()  # pyright: ignore[reportPrivateUsage]  -- reset between tests
    models.Base.metadata.create_all(db.engine())
    yield
    db.engine().dispose()
    db.engine.cache_clear()
    db._sessions.cache_clear()  # pyright: ignore[reportPrivateUsage]  -- reset between tests
