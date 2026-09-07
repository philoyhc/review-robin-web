from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from _sqlite_schema import build_sqlite_schema
from app.auth.identity import AuthenticatedUser, get_current_user
from app.config import settings
from app.db.models import Instrument, InstrumentViewPolicy, ReviewSession
from app.db.session import get_db
from app.services import visibility_policies
from app.main import app


# The Segment 16A PR 1 operator-allowlist gate is mounted on the
# parent operator router (``app/web/routes_operator/__init__.py``),
# so every route under ``/operator/*`` redirects unallowlisted
# identities to ``/me`` (18R Item 6). The fixtures below seed
# ``alice`` / ``bob`` via the ``OPERATOR_EMAILS`` env-var bootstrap
# so first-sign-in flips ``is_operator=True`` on user-row creation
# — preserving the pre-16A test contract that ``client(alice)``
# can reach operator routes.
#
# Tests that explicitly exercise the gate (e.g.
# ``test_operator_allowlist_gate.py``) carry their own
# ``_reset_allowlists`` autouse fixture that clears these,
# overriding the conftest-level seeding for that file only.
_TEST_OPERATOR_EMAILS = ("alice@example.edu", "bob@example.edu")


@pytest.fixture
def grant_reviewee_visibility(db: Session) -> Callable[..., Instrument]:
    """Fixture wrapper around :func:`_grant_reviewee_visibility`.

    A fixture rather than an importable helper because
    ``tests/conftest.py`` shadows this module's name on the import path
    — ``from conftest import …`` in an integration test resolves to the
    *parent* conftest and fails.
    """

    def _grant(
        review_session: ReviewSession, *, mode: str = "raw"
    ) -> Instrument:
        return _grant_reviewee_visibility(db, review_session, mode=mode)

    return _grant


def _grant_reviewee_visibility(
    db: Session, review_session: ReviewSession, *, mode: str = "raw"
) -> Instrument:
    """Give the session's ``reviewee`` audience a grant that resolves
    **right now**, and return the instrument carrying it.

    Segment 19F PR 2 made a reviewee's ``/me`` row conditional on such a
    grant, so a test that wants a *reviewee* row (rather than merely a
    row) has to create one. Two things are needed together and neither
    is sufficient alone:

    * an open response-release window, which since 19F PR 2a needs
      **three** things and not two: the session ``expired``,
      `responses_release_at` in the past, and `responses_release_until`
      unset. Responses are released *because the session is over*, so
      closing it is part of granting, not a separate step a caller can
      forget; and
    * an ``instrument_view_policies`` row for the ``reviewee`` audience
      whose **after_release** pair is set.

    Callers that need a different lifecycle state should set it
    *after* calling this — and expect no grant, which is the point.

    The ``while_ongoing`` pair is deliberately left off: reviewees may
    never see responses mid-flight, so that cell is invalid for them by
    construction (`visibility_policies._PER_CELL_VALID_MODES`) and
    setting it here would encode a state the editor cannot produce.
    """
    granularity, identification = visibility_policies.MODE_LABELS[mode]
    instrument = Instrument(
        session_id=review_session.id,
        name="Feedback",
        order=1,
    )
    db.add(instrument)
    db.flush()
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="reviewee",
            after_release_granularity=granularity,
            after_release_identification=identification,
        )
    )
    review_session.status = "expired"
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    review_session.responses_release_until = None
    db.commit()
    return instrument


@pytest.fixture(autouse=True)
def _seed_test_operator_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "operator_emails", list(_TEST_OPERATOR_EMAILS))


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
    """Fresh per-test SQLite engine with the full schema built.
    Routes commit to disk; a separate Session can verify persistence.

    Builds the schema from ORM metadata (``build_sqlite_schema``)
    rather than replaying the migration chain — the same fast path the
    session-scoped ``engine`` fixture takes."""
    db_path = tmp_path / "regression.db"
    eng = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    build_sqlite_schema(eng)
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
