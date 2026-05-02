from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """In-memory SQLite engine with the full Alembic migration applied."""
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    # Mirror the production-side FK enforcement so ``ON DELETE CASCADE``
    # actually fires in tests. SQLite ships with FKs off by default.
    from app.db.session import _enable_sqlite_fk_enforcement

    _enable_sqlite_fk_enforcement(eng)

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
