from __future__ import annotations

import os
import re

# Flip ``settings.audit_strict_mode`` on for the test session before
# anything imports ``app.config`` (Pydantic-settings reads env vars
# at instantiation time). Strict mode raises
# ``AuditDetailValidationError`` on any audit-detail shape violation
# so drift back into the pre-canonical idiosyncratic shapes surfaces
# in CI rather than silently logging in production. See Segment 11K
# PR 8 and ``spec/architecture.md`` "Audit-event detail schema".
os.environ.setdefault("AUDIT_STRICT_MODE", "true")

# Rehydrate ships gated off (Segment 19N) — see ``app/config.py``. The
# machinery is wired and worth keeping covered, so the suite runs with
# it on; ``tests/integration/test_rehydrate_gate.py`` pins the shipped default
# to off so turning it on here cannot hide that.
os.environ.setdefault("REHYDRATE_ENABLED", "true")

# A developer's ``.env`` (the dev container writes one from
# ``.env.example``) sets ``ALLOW_FAKE_AUTH=true``, which folds the fake
# identity into the super-admin set (``app/auth/roles.py``) and fails the
# "no super tier configured" tests. Pin it off, as CI has it; a test that
# needs fake auth turns it on itself. An environment variable outranks
# ``.env`` in pydantic-settings, so this holds whatever the file says.
os.environ["ALLOW_FAKE_AUTH"] = "false"

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import Engine, create_engine, make_url, text  # noqa: E402
from sqlalchemy.exc import ProgrammingError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from _sqlite_schema import build_sqlite_schema  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


def _test_database_url() -> str:
    """``TEST_DATABASE_URL``, else in-memory SQLite — never ``DATABASE_URL``.

    The Postgres path below runs ``DROP SCHEMA public CASCADE``, so a
    fallback to ``DATABASE_URL`` let a bare ``pytest`` in a shell that had
    exported the app's database wipe it (findings H12). Only a URL named
    for the tests reaches the drop."""
    return os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL


_WORKER = re.compile(r"gw\d+")
_DATABASE_NAME = re.compile(r"[A-Za-z0-9_]+")


def _worker_database_url(url: str, worker: str | None) -> str:
    """The database this xdist worker runs on (segment 22B).

    Serial runs and SQLite keep ``url``. Under xdist on Postgres each
    worker takes the named database plus its id (``rrw`` -> ``rrw_gw0``),
    so the schema drop below never touches another worker's tables, and a
    rerun reuses the same databases rather than adding more."""
    if not worker or url.startswith("sqlite"):
        return url
    if not _WORKER.fullmatch(worker):
        raise RuntimeError(f"unexpected xdist worker id {worker!r}")
    parsed = make_url(url)
    name = f"{parsed.database}_{worker}"
    if not _DATABASE_NAME.fullmatch(name):
        raise RuntimeError(f"cannot derive a worker database from {parsed.database!r}")
    return parsed.set(database=name).render_as_string(hide_password=False)


def _ensure_database(connection, name: str) -> None:
    """Create ``name`` on an autocommit connection unless it exists. Only
    a derived worker database reaches here, never a named one."""
    exists = connection.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
    ).scalar()
    if exists:
        return
    try:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    except ProgrammingError as error:
        raise RuntimeError(
            f"cannot create the worker database {name!r}: the role in "
            "TEST_DATABASE_URL needs CREATEDB to run the suite under xdist "
            "on Postgres (run it serially, without -n, otherwise)"
        ) from error


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Engine for the test session.

    Defaults to in-memory SQLite, where the schema is built directly
    from the ORM metadata (``Base.metadata.create_all``) — the
    40-migration replay is pure session-startup cost that ``create_all``
    skips. The migration chain is still exercised on every PR by the
    ``ci-postgres`` job, so SQLite tests can take the fast path.

    When ``TEST_DATABASE_URL`` points at Postgres,
    runs the suite against that DB with the full Alembic migration
    applied so CI exercises both dialect divergence and the migration
    round-trip the SQLite path now skips. Under xdist each worker runs on
    its own database derived from it, created if missing
    (``_worker_database_url``, segment 22B).
    """
    named = _test_database_url()
    url = _worker_database_url(named, os.environ.get("PYTEST_XDIST_WORKER"))
    is_sqlite = url.startswith("sqlite")
    if url != named:
        admin = create_engine(named, isolation_level="AUTOCOMMIT", future=True)
        try:
            with admin.connect() as connection:
                _ensure_database(connection, make_url(url).database)
        finally:
            admin.dispose()

    connect_args: dict[str, object] = {}
    if is_sqlite:
        connect_args["check_same_thread"] = False
    eng = create_engine(url, connect_args=connect_args, future=True)

    if is_sqlite:
        # Mirror the production-side FK enforcement so ``ON DELETE CASCADE``
        # actually fires in tests. SQLite ships with FKs off by default.
        from app.db.session import _enable_sqlite_fk_enforcement

        _enable_sqlite_fk_enforcement(eng)
        build_sqlite_schema(eng)
        yield eng
        eng.dispose()
        return

    # Postgres CI service container may carry over schema between job
    # retries on the same runner; start from a clean slate so the
    # migration round-trip is deterministic.
    with eng.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    with eng.connect() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
        connection.commit()

    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Per-test transactional session that rolls back on teardown.

    Suitable for tests that only flush(). Integration tests that need
    to tolerate service-layer commit() calls override this with a
    savepoint-based fixture in tests/integration/conftest.py.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# Per-session ``response_type_definitions`` table retired
# 2026-05-26 — the legacy RTD seed shim that lived here is gone.
# Tests that need a Rating-Integer-1-5 inline default get it from
# ``DEFAULT_RESPONSE_FIELDS[0]`` via the standard creators.
