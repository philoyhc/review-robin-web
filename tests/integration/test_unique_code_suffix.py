"""Clone and rehydrate derive a fresh code and name by adding a suffix.

A source code already at the column's 64 characters (or a name at 255)
used to have the suffix cut off by the truncation, so every candidate
was the source's own value, taken, and the search loop never ended.
The base is trimmed now, so each candidate is distinct and fits."""
from __future__ import annotations

import signal
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.sessions import SessionCreate
from app.services import session_clone, session_rehydrate, sessions

LONG_CODE = "c" * 64
LONG_NAME = "n" * 255


@pytest.fixture(autouse=True)
def _fail_instead_of_hang() -> Iterator[None]:
    """The old bug was an endless loop, so a regression would stall the
    run rather than fail it: time each test out after 10 seconds.
    ``SIGALRM`` is POSIX only; on Windows (``docs/local_setup.md`` §10)
    the tests run without the guard."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def _timeout(signum: int, frame: object) -> None:
        raise TimeoutError("candidate search did not terminate")

    previous = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(10)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def _operator(db: Session) -> User:
    op = User(email="op-suffix@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    return op


def test_clone_of_a_64_char_code_gets_distinct_codes_that_fit(
    db: Session,
) -> None:
    op = _operator(db)
    source = sessions.create_session(
        db, user=op, payload=SessionCreate(name="Long code", code=LONG_CODE)
    )

    first = session_clone.clone_session(db, source=source, user=op, mode="config")
    second = session_clone.clone_session(db, source=source, user=op, mode="config")

    assert first.code == "c" * 59 + "-copy"
    assert second.code == "c" * 57 + "-copy-2"


def test_rehydrate_names_for_a_64_char_code_and_255_char_name(
    db: Session,
) -> None:
    op = _operator(db)
    sessions.create_session(
        db, user=op, payload=SessionCreate(name=LONG_NAME, code=LONG_CODE)
    )
    taken = "c" * 58 + "-rehyd"
    sessions.create_session(
        db, user=op, payload=SessionCreate(name="n" * 249 + "_REHYD", code=taken)
    )

    code = session_rehydrate.derive_unique_code(db, original_code=LONG_CODE)
    name = session_rehydrate.derive_rehydrate_name(
        db, user=op, original_name=LONG_NAME
    )

    assert code == "c" * 56 + "-rehyd-2"
    assert name == "n" * 247 + "_REHYD_1"
