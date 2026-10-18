"""The observer's CSV address names the instrument by its per-session
number (19V Item 3).

``/me/sessions/{public_id}/collation/instruments/{instrument_seq}.csv``.
``instruments.id`` is workspace-wide, so an address carrying it let a
participant read off how many instruments the workspace has made. These
tests pad the workspace with another session's instruments first, so the
ID and the number differ and a test cannot pass by reading the wrong one.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession

from .test_observer_collation_body import (
    _MATH_RULE,
    _add_observer,
    _make_session,
    _seed_one_instrument,
)


def _pad_workspace(client: TestClient, db: Session) -> ReviewSession:
    """Another session holding five instruments, created first. Its
    fifth is observed just as the session under test's is, so only the
    route's session scope keeps it out of that session's reach."""
    other = _make_session(client, db, code="col-addr-padding")
    db.add_all(
        [Instrument(session_id=other.id, name=f"Pad {n}", order=n + 1) for n in range(3)]
    )
    db.flush()
    observed = _seed_one_instrument(db, other)["instrument"]
    assert observed.session_seq == 5
    _add_observer(db, other, email="alice@example.edu", cohort_rule=_MATH_RULE)
    return other


def _observed_instrument(client: TestClient, db: Session, code: str) -> tuple[ReviewSession, Instrument]:
    _pad_workspace(client, db)
    review_session = _make_session(client, db, code=code)
    instrument = _seed_one_instrument(db, review_session)["instrument"]
    _add_observer(db, review_session, email="alice@example.edu", cohort_rule=_MATH_RULE)
    db.commit()
    assert instrument.id != instrument.session_seq
    return review_session, instrument


def _csv(review_session: ReviewSession, handle: object) -> str:
    return f"/me/sessions/{review_session.public_id}/collation/instruments/{handle}.csv"


def test_the_download_link_names_the_per_session_number(
    client: TestClient, db: Session
) -> None:
    review_session, instrument = _observed_instrument(client, db, "col-addr-link")

    body = client.get(f"/me/sessions/{review_session.public_id}/collation").text

    assert f'href="{_csv(review_session, instrument.session_seq)}"' in body
    assert f"instruments/{instrument.id}.csv" not in body


def test_the_number_reaches_the_csv_and_the_id_does_not(
    client: TestClient, db: Session
) -> None:
    review_session, instrument = _observed_instrument(client, db, "col-addr-reach")

    assert client.get(_csv(review_session, instrument.session_seq)).status_code == 200
    # No instrument in this session carries the ID as its number.
    assert client.get(_csv(review_session, instrument.id)).status_code == 404


@pytest.mark.parametrize(
    "handle", ["999", "abc", "1e3", "-1", "0", "02", "99999999999999999999", "2%00"]
)
def test_an_unknown_or_malformed_number_answers_404(
    client: TestClient, db: Session, handle: str
) -> None:
    review_session, _ = _observed_instrument(client, db, "col-addr-unknown")

    assert client.get(_csv(review_session, handle)).status_code == 404


def test_another_sessions_number_reaches_nothing_here(
    client: TestClient, db: Session
) -> None:
    """The padding session's instruments run to number 5, the fifth
    observed by the same address; this session's run to 2. Number 5 is
    the other session's instrument, and out of reach here.

    Two scopes keep it so, the route's lookup and the cohort's
    ``Assignment.session_id``; either alone holds this test green, and
    dropping both turns it red."""
    review_session, _ = _observed_instrument(client, db, "col-addr-other")

    assert client.get(_csv(review_session, 5)).status_code == 404
