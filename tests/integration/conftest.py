from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.main import app


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
