from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.auth.identity import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Per-test transactional session bound to the migrated SQLite engine.

    Uses the canonical "savepoint per commit" recipe so service-layer
    ``commit()`` calls release a SAVEPOINT and the outer transaction can
    still be rolled back on teardown.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess: Session, trans: object) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _make_client(
    db: Session,
    user: AuthenticatedUser,
) -> TestClient:
    def override_get_db() -> Iterator[Session]:
        yield db

    def override_get_current_user() -> AuthenticatedUser:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


@pytest.fixture
def alice() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="alice-oid",
        email="alice@example.edu",
        name="Alice Example",
        provider="aad",
    )


@pytest.fixture
def bob() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="bob-oid",
        email="bob@example.edu",
        name="Bob Example",
        provider="aad",
    )


@pytest.fixture
def client(db: Session, alice: AuthenticatedUser) -> Iterator[TestClient]:
    """TestClient signed in as alice. Override get_current_user mid-test for
    multi-user scenarios."""
    test_client = _make_client(db, alice)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def make_client(db: Session) -> Iterator[object]:
    """Factory that returns a TestClient signed in as any AuthenticatedUser."""

    def _factory(user: AuthenticatedUser) -> TestClient:
        return _make_client(db, user)

    try:
        yield _factory
    finally:
        app.dependency_overrides.clear()


# --- "Real-commit" harness ---------------------------------------------------
#
# The default `db` fixture above wraps every request in a SAVEPOINT, so a
# service that forgets to call ``db.commit()`` still appears to persist data
# (the test session shares a connection with the route). Production routes
# don't get that safety net — each request opens its own connection and
# closes it without committing if the service didn't commit explicitly.
#
# The fixtures below give a regression harness that catches that class of
# bug. They use a tmp-file SQLite engine with the full migration applied,
# create a fresh ``Session`` per request via the production sessionmaker
# pattern, and let tests verify persistence via a *separate* ``Session``
# bound to the same engine (different connection). If a service forgets
# to commit, the verification session will see the un-mutated state and
# the test will fail.


@pytest.fixture
def committed_engine(tmp_path: Path) -> Iterator[Engine]:
    """Fresh per-test SQLite engine with the full migration applied.
    Routes commit to disk; a separate Session can verify persistence."""
    db_path = tmp_path / "regression.db"
    eng = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{db_path}")
    with eng.connect() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
        connection.commit()
    yield eng
    eng.dispose()


@pytest.fixture
def committed_client(
    committed_engine: Engine, alice: AuthenticatedUser
) -> Iterator[TestClient]:
    """TestClient whose routes commit to ``committed_engine`` (no SAVEPOINT
    isolation). Pair with ``committed_engine`` and a fresh ``Session`` to
    verify persistence after each route call."""
    SessionLocal = sessionmaker(
        bind=committed_engine, autoflush=False, expire_on_commit=False
    )

    def override_get_db() -> Iterator[Session]:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_get_current_user() -> AuthenticatedUser:
        return alice

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
