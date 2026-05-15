"""Cookie persistence for the reviewer-surface sort —
Segment 13B Part 2 PR 5.

Pins:

- The cookie name follows the
  ``rrw-sort-rs-{session_id}-{instrument_id}`` convention so the
  SSR layer can find it for the right instrument.
- The route reads the cookie at render time and threads the
  decoded spec through ``views.order_rows_by_sort_spec`` so the
  initial HTML lands in the persisted order — no JS-reorder
  flicker.
- Malformed / tampered cookies are silently ignored (initial
  render falls back to the operator default).
- The shared ``base.html`` script ships the cookie I/O helpers
  + the ``DOMContentLoaded`` hydration pass.
"""
from __future__ import annotations

import json
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Instrument, InstrumentDisplayField, ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _setup_session_with_three_reviewees(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
) -> ReviewSession:
    operator_client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nR,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    b"RevieweeName,RevieweeEmail\n"
                    b"Bravo,bravo@example.edu\n"
                    b"Alpha,alpha@example.edu\n"
                    b"Charlie,charlie@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    return review_session


def _activate(
    operator_client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    operator_client.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    response = operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)


def _instrument(db: Session, review_session: ReviewSession) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


# --- Table marker --------------------------------------------------------


def test_table_marker_uses_cookie_name_shape(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """The ``data-rrw-sortable`` attribute value is the cookie
    name. Shape: ``rrw-sort-rs-{session_id}-{instrument_id}``."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="ck-marker", reviewer_email=rae.email
    )
    instrument = _instrument(db, review_session)
    _activate(client, db, review_session)
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    assert response.status_code == 200
    body = response.text
    expected = (
        f'data-rrw-sortable="rrw-sort-rs-{review_session.id}'
        f'-{instrument.id}"'
    )
    assert expected in body


# --- SSR round-trip ------------------------------------------------------


def test_cookie_drives_ssr_initial_row_order(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """A valid cookie reorders the rendered rows on the first
    page load — no JS roundtrip needed."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="ck-ssr", reviewer_email=rae.email
    )
    instrument = _instrument(db, review_session)
    _activate(client, db, review_session)

    rae_client = make_client(rae)
    cookie_name = f"rrw-sort-rs-{review_session.id}-{instrument.id}"
    rae_client.cookies.set(
        cookie_name,
        json.dumps([{"key": "reviewee.name", "dir": "desc"}]),
        path=f"/reviewer/sessions/{review_session.id}",
    )
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    body = response.text
    # Reverse-alphabetical: Charlie, Bravo, Alpha.
    assert body.find("Charlie") < body.find("Bravo") < body.find("Alpha")


def test_percent_encoded_cookie_drives_ssr_row_order(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """The browser primitive writes the cookie percent-encoded
    (``encodeURIComponent``); the SSR decoder must ``unquote``
    before parsing or the server silently ignores the sort."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="ck-enc", reviewer_email=rae.email
    )
    instrument = _instrument(db, review_session)
    _activate(client, db, review_session)

    rae_client = make_client(rae)
    cookie_name = f"rrw-sort-rs-{review_session.id}-{instrument.id}"
    rae_client.cookies.set(
        cookie_name,
        quote(json.dumps([{"key": "reviewee.name", "dir": "desc"}])),
        path=f"/reviewer/sessions/{review_session.id}",
    )
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    ).text
    assert body.find("Charlie") < body.find("Bravo") < body.find("Alpha")


def test_cookie_overrides_operator_default(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Operator default is desc-by-name. Reviewer's cookie is
    asc-by-name. The cookie wins."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="ck-override", reviewer_email=rae.email
    )
    instrument = _instrument(db, review_session)
    name_field = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .where(InstrumentDisplayField.source_field == "name")
    ).scalar_one()
    instrument.sort_display_fields = [
        {"display_field_id": name_field.id, "dir": "desc"}
    ]
    db.commit()
    _activate(client, db, review_session)

    rae_client = make_client(rae)
    cookie_name = f"rrw-sort-rs-{review_session.id}-{instrument.id}"
    rae_client.cookies.set(
        cookie_name,
        json.dumps([{"key": "reviewee.name", "dir": "asc"}]),
        path=f"/reviewer/sessions/{review_session.id}",
    )
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    body = response.text
    # Cookie's asc wins over operator's desc.
    assert body.find("Alpha") < body.find("Bravo") < body.find("Charlie")


def test_malformed_cookie_falls_back_to_operator_default(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """A malformed JSON cookie is silently ignored; render falls
    back to the operator default (or insertion order if no
    default)."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="ck-bad", reviewer_email=rae.email
    )
    instrument = _instrument(db, review_session)
    name_field = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .where(InstrumentDisplayField.source_field == "name")
    ).scalar_one()
    instrument.sort_display_fields = [
        {"display_field_id": name_field.id, "dir": "asc"}
    ]
    db.commit()
    _activate(client, db, review_session)

    rae_client = make_client(rae)
    cookie_name = f"rrw-sort-rs-{review_session.id}-{instrument.id}"
    rae_client.cookies.set(
        cookie_name,
        "not-json{",
        path=f"/reviewer/sessions/{review_session.id}",
    )
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    assert response.status_code == 200
    body = response.text
    # Operator default (asc) wins because the malformed cookie
    # is dropped.
    assert body.find("Alpha") < body.find("Bravo") < body.find("Charlie")


def test_cookie_response_key_dropped_server_side(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """``response:N`` keys are JS-only — the server can't sort by
    response values. The decoder drops them; the rest of the
    spec still applies."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="ck-rkey", reviewer_email=rae.email
    )
    instrument = _instrument(db, review_session)
    _activate(client, db, review_session)

    rae_client = make_client(rae)
    cookie_name = f"rrw-sort-rs-{review_session.id}-{instrument.id}"
    # response:99 should drop; reviewee.name asc should apply.
    rae_client.cookies.set(
        cookie_name,
        json.dumps([
            {"key": "response:99", "dir": "asc"},
            {"key": "reviewee.name", "dir": "asc"},
        ]),
        path=f"/reviewer/sessions/{review_session.id}",
    )
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    body = response.text
    assert body.find("Alpha") < body.find("Bravo") < body.find("Charlie")


# --- Base.html primitive guards -----------------------------------------


def test_shared_primitive_ships_cookie_helpers(
    client: TestClient,
) -> None:
    """Regression guard: ``base.html`` carries the cookie I/O
    helpers + the ``DOMContentLoaded`` hydration pass."""
    response = client.get("/operator/sessions")
    body = response.text
    assert "function _rrwWriteCookie" in body
    assert "function _rrwReadCookie" in body
    assert "function _rrwHydrateFromCookies" in body
    assert "DOMContentLoaded" in body
