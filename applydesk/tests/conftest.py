"""ApplyDesk's tests run signed in as the fake local super-admin, whatever
the developer's `.env` says; a test that needs someone else changes the
settings itself."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, make_url, text
from starlette.testclient import TestClient

from cordware.settings import identity_settings

_WORKER = re.compile(r"gw\d+")
_NAME = re.compile(r"[A-Za-z0-9_]{1,63}")


def _postgres_url() -> str | None:
    """Apply Desk's own test database on Postgres (AD-128, segment AD2C):
    derived from ``TEST_DATABASE_URL`` as ``<db>_ad``, or ``<db>_ad_gw0``
    and on under xdist, so neither RRW's schema drop (`tests/conftest.py`)
    nor another worker touches it. None runs every test on SQLite."""
    named = os.environ.get("TEST_DATABASE_URL", "")
    if not named or named.startswith("sqlite"):
        return None
    parsed = make_url(named)
    worker = os.environ.get("PYTEST_XDIST_WORKER", "")
    if worker and not _WORKER.fullmatch(worker):
        raise RuntimeError(f"unexpected xdist worker id {worker!r}")
    name = f"{parsed.database}_ad" + (f"_{worker}" if worker else "")
    if not _NAME.fullmatch(name):
        raise RuntimeError(f"cannot derive Apply Desk's test database from {parsed.database!r}")
    admin = create_engine(named, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            found = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            ).scalar()
            if not found:
                connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()
    return parsed.set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def _applydesk_postgres() -> Iterator[str | None]:
    """On Postgres, Apply Desk's tables are made once per session, from the
    models (the migration is round-tripped in `ci-postgres` itself)."""
    url = _postgres_url()
    if url is None:
        yield None
        return
    from applydesk import models

    made = create_engine(url)
    # The whole schema, not the models' tables alone: a table a later
    # change drops from the models would otherwise outlive it and block
    # the drop by its foreign keys. The database is the tests' own.
    with made.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    models.Base.metadata.create_all(made)
    made.dispose()
    yield url


@pytest.fixture(autouse=True)
def _browser_like_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test client posts as a current browser does, naming its own
    site in ``Sec-Fetch-Site`` (AD-126 refuses a post with neither that nor
    a same-origin ``Origin`` or ``Referer``). A test of an older browser
    takes the header out: ``client.headers.pop("sec-fetch-site")``."""
    real = TestClient.__init__

    def init(self: TestClient, *args: Any, **kwargs: Any) -> None:
        real(self, *args, **kwargs)
        self.headers.setdefault("sec-fetch-site", "same-origin")

    monkeypatch.setattr(TestClient, "__init__", init)


@pytest.fixture(autouse=True)
def _fake_super_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "app_env", "local")
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    monkeypatch.setattr(identity_settings, "fake_auth_email", "admin@example.edu")
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", True)
    monkeypatch.setattr(identity_settings, "super_admin_emails", [])


@pytest.fixture(autouse=True)
def applydesk_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    _applydesk_postgres: str | None,
) -> Iterator[None]:
    """Apply Desk's database as a fresh SQLite file for every test, its
    tables made from the models (the migration is round-tripped in
    `test_applydesk_db.py`): the gate reads it (segment AD2A), so no test
    may reach a developer's `./applydesk.db`. With ``TEST_DATABASE_URL``
    on Postgres (`ci-postgres`), it is that run's own database, every
    table emptied before each test (AD-128)."""
    from applydesk import db, models

    url = _applydesk_postgres or f"sqlite:///{tmp_path / 'applydesk.db'}"
    monkeypatch.setenv("APPLYDESK_DATABASE_URL", url)
    db.engine.cache_clear()
    db._sessions.cache_clear()  # pyright: ignore[reportPrivateUsage]  -- reset between tests
    if _applydesk_postgres:
        names = ", ".join(f'"{t.name}"' for t in models.Base.metadata.sorted_tables)
        with db.engine().begin() as connection:
            connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    else:
        models.Base.metadata.create_all(db.engine())
    # The fake identity owns the sample exercises in the ordinary way, as
    # Local Operator does after `python -m applydesk.seed`: the super-admin
    # reaches no exercise it holds no role on (segment AD2M). A test of an
    # unloaded database asks for `unseeded`.
    if "unseeded" not in request.fixturenames:
        from applydesk import seed

        session = db.new_session()
        # Settings recorded, as the localhost seed records them (segment
        # AD2B rung 3): Details saves against them and refuses a code
        # another exercise holds.
        seed.seed(session)
        session.close()
    yield
    db.engine().dispose()
    db.engine.cache_clear()
    db._sessions.cache_clear()  # pyright: ignore[reportPrivateUsage]  -- reset between tests


@pytest.fixture
def unseeded() -> None:
    """Asked for by a test of a database the seed has not loaded: the
    `applydesk_db` fixture then leaves it empty."""
