from __future__ import annotations

import os

# Flip ``settings.audit_strict_mode`` on for the test session before
# anything imports ``app.config`` (Pydantic-settings reads env vars
# at instantiation time). Strict mode raises
# ``AuditDetailValidationError`` on any audit-detail shape violation
# so drift back into the pre-canonical idiosyncratic shapes surfaces
# in CI rather than silently logging in production. See Segment 11K
# PR 8 and ``spec/architecture.md`` "Audit-event detail schema".
os.environ.setdefault("AUDIT_STRICT_MODE", "true")

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import Engine, create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


def _test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get(
        "DATABASE_URL", DEFAULT_TEST_DATABASE_URL
    )


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Engine for the test session with the full Alembic migration applied.

    Defaults to in-memory SQLite. When ``TEST_DATABASE_URL`` (or
    ``DATABASE_URL``) points at Postgres, runs the suite against that DB
    so CI can exercise dialect divergence the SQLite path hides.
    """
    url = _test_database_url()
    is_sqlite = url.startswith("sqlite")

    connect_args: dict[str, object] = {}
    if is_sqlite:
        connect_args["check_same_thread"] = False
    eng = create_engine(url, connect_args=connect_args, future=True)

    if is_sqlite:
        # Mirror the production-side FK enforcement so ``ON DELETE CASCADE``
        # actually fires in tests. SQLite ships with FKs off by default.
        from app.db.session import _enable_sqlite_fk_enforcement

        _enable_sqlite_fk_enforcement(eng)
    else:
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
