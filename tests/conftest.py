from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

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
