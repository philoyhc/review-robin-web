"""Route + service coverage for the Participants-platform
release-responses window (W14 + S12 — wires
`responses_release_at` + `responses_release_until` on both the
Create New Session and Session Details edit forms).

S12 retired the W14 ISO 8601 offset
(`release_until_offset`) in favour of an absolute close
datetime (`responses_release_until`) — the form input is now
a `datetime-local` and the Stop release button (forthcoming)
writes the same column.

The §8.2.2 anchor-null rule (inertness when
`responses_release_at` is NULL) is enforced at view time, not
save time — persisting an until without an anchor is allowed
and harmless. These tests pin the save-time contract:
parseability, ordering, magnitude check, and round-trip
prefill on edit.
"""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _naive_utc(value: datetime | None) -> datetime | None:
    """Strip tzinfo so comparisons read uniformly on both SQLite
    (which drops the tz on read) and Postgres."""
    return value.replace(tzinfo=None) if value is not None else None


def _make_session(
    client: TestClient,
    db: Session,
    *,
    code: str,
    data: dict[str, str] | None = None,
) -> ReviewSession:
    payload = {"name": "S", "code": code, "description": ""}
    if data:
        payload.update(data)
    response = client.post(
        "/operator/sessions", data=payload, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _submit_edit(
    client: TestClient,
    review_session: ReviewSession,
    **overrides: str,
) -> int:
    data: dict[str, str] = {
        "name": review_session.name,
        "code": review_session.code,
        "description": review_session.description or "",
        "display_timezone": "",
    }
    data.update(overrides)
    response = client.post(
        f"/operator/sessions/{review_session.id}/edit",
        data=data,
        follow_redirects=False,
    )
    return response.status_code


# ── Create-session route ──────────────────────────────────────────────


def test_create_persists_release_window_pair(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client,
        db,
        code="rw-create",
        data={
            "responses_release_at": "2027-01-01T12:00",
            "responses_release_until": "2027-01-31T12:00",
            "display_timezone": "UTC",
        },
    )
    db.refresh(review_session)
    assert _naive_utc(review_session.responses_release_at) == datetime(
        2027, 1, 1, 12, 0
    )
    assert _naive_utc(review_session.responses_release_until) == datetime(
        2027, 1, 31, 12, 0
    )


def test_create_allows_until_without_anchor(
    client: TestClient, db: Session
) -> None:
    """The §8.2.2 anchor-null rule is enforced at view time; save
    allows an until alone, which the consumer will treat as inert
    until the anchor is set. Magnitude / ordering checks skip when
    the anchor is NULL."""
    review_session = _make_session(
        client,
        db,
        code="rw-until-only",
        data={
            "responses_release_until": "2027-02-15T12:00",
            "display_timezone": "UTC",
        },
    )
    db.refresh(review_session)
    assert review_session.responses_release_at is None
    assert _naive_utc(review_session.responses_release_until) == datetime(
        2027, 2, 15, 12, 0
    )


def test_create_rejects_malformed_release_at(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "rw-bad-at",
            "description": "",
            "responses_release_at": "not-a-date",
            "display_timezone": "UTC",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "Release responses from" in response.text


def test_create_rejects_malformed_until(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "rw-bad-until",
            "description": "",
            "responses_release_until": "30 days",
            "display_timezone": "UTC",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "Release responses until" in response.text


def test_create_rejects_until_at_or_before_anchor(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "rw-out-of-order",
            "description": "",
            "responses_release_at": "2027-01-15T12:00",
            "responses_release_until": "2027-01-15T12:00",
            "display_timezone": "UTC",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "after Release responses from" in response.text


def test_create_rejects_until_exceeding_365d_from_anchor(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "rw-too-far",
            "description": "",
            "responses_release_at": "2027-01-01T00:00",
            "responses_release_until": "2028-02-01T00:00",
            "display_timezone": "UTC",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "within 365 days" in response.text


# ── Edit route ────────────────────────────────────────────────────────


def test_edit_persists_release_window_pair(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rw-edit")
    code = _submit_edit(
        client,
        review_session,
        responses_release_at="2027-02-01T09:30",
        responses_release_until="2027-02-08T09:30",
        display_timezone="UTC",
    )
    assert code == 303
    db.refresh(review_session)
    assert _naive_utc(review_session.responses_release_at) == datetime(
        2027, 2, 1, 9, 30
    )
    assert _naive_utc(review_session.responses_release_until) == datetime(
        2027, 2, 8, 9, 30
    )


def test_edit_clears_release_window_on_blank_input(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client,
        db,
        code="rw-clear",
        data={
            "responses_release_at": "2027-01-01T12:00",
            "responses_release_until": "2027-01-31T12:00",
            "display_timezone": "UTC",
        },
    )
    code = _submit_edit(
        client,
        review_session,
        responses_release_at="",
        responses_release_until="",
        display_timezone="UTC",
    )
    assert code == 303
    db.refresh(review_session)
    assert review_session.responses_release_at is None
    assert review_session.responses_release_until is None


def test_edit_form_prefills_saved_release_window_values(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client,
        db,
        code="rw-prefill",
        data={
            "responses_release_at": "2027-03-01T10:00",
            "responses_release_until": "2027-03-15T10:00",
            "display_timezone": "UTC",
        },
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/edit"
    ).text
    # Both inputs prefilled in session zone (UTC).
    assert 'value="2027-03-01T10:00"' in body
    assert 'value="2027-03-15T10:00"' in body


def test_edit_until_renders_as_datetime_local_input(
    client: TestClient, db: Session
) -> None:
    """S12 swapped the text+ISO-duration input to a
    ``datetime-local``. The text input shape is gone."""
    review_session = _make_session(client, db, code="rw-shape")
    body = client.get(
        f"/operator/sessions/{review_session.id}/edit"
    ).text
    assert (
        'type="datetime-local" id="responses_release_until"' in body
    )
    assert 'name="release_until_offset"' not in body
