"""Route + service coverage for the Participants-platform
release-responses window (W14 — wires
`responses_release_at` + `release_until_offset` on both the
Create New Session and Session Details edit forms).

The §8.2.2 anchor-null rule (inertness when
`responses_release_at` is NULL) is enforced at view time, not
save time — persisting a `release_until_offset` without an
anchor is allowed and harmless. These tests pin the save-time
contract: parseability, positivity, magnitude cap, and round-
trip prefill on edit.
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
            "release_until_offset": "P30D",
            "display_timezone": "UTC",
        },
    )
    db.refresh(review_session)
    # SQLite drops tzinfo on read; compare against the naive form.
    assert _naive_utc(review_session.responses_release_at) == datetime(
        2027, 1, 1, 12, 0
    )
    assert review_session.release_until_offset == "P30D"


def test_create_allows_offset_without_anchor(
    client: TestClient, db: Session
) -> None:
    """The §8.2.2 anchor-null rule is enforced at view time; save
    allows an offset alone, which the consumer will treat as
    inert until the anchor is set."""
    review_session = _make_session(
        client,
        db,
        code="rw-offset-only",
        data={"release_until_offset": "P14D"},
    )
    db.refresh(review_session)
    assert review_session.responses_release_at is None
    assert review_session.release_until_offset == "P14D"


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


def test_create_rejects_malformed_offset(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "rw-bad-offset",
            "description": "",
            "release_until_offset": "30 days",
            "display_timezone": "UTC",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_create_rejects_zero_or_negative_offset(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "rw-neg",
            "description": "",
            "release_until_offset": "-P1D",
            "display_timezone": "UTC",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "must be positive" in response.text


def test_create_rejects_oversized_offset(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "rw-big",
            "description": "",
            "release_until_offset": "P9999D",
            "display_timezone": "UTC",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "maximum window length" in response.text


# ── Edit route ────────────────────────────────────────────────────────


def test_edit_persists_release_window_pair(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rw-edit")
    code = _submit_edit(
        client,
        review_session,
        responses_release_at="2027-02-01T09:30",
        release_until_offset="P7D",
        display_timezone="UTC",
    )
    assert code == 303
    db.refresh(review_session)
    assert _naive_utc(review_session.responses_release_at) == datetime(
        2027, 2, 1, 9, 30
    )
    assert review_session.release_until_offset == "P7D"


def test_edit_clears_release_window_on_blank_input(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client,
        db,
        code="rw-clear",
        data={
            "responses_release_at": "2027-01-01T12:00",
            "release_until_offset": "P30D",
            "display_timezone": "UTC",
        },
    )
    code = _submit_edit(
        client,
        review_session,
        responses_release_at="",
        release_until_offset="",
        display_timezone="UTC",
    )
    assert code == 303
    db.refresh(review_session)
    assert review_session.responses_release_at is None
    assert review_session.release_until_offset is None


def test_edit_form_prefills_saved_release_window_values(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client,
        db,
        code="rw-prefill",
        data={
            "responses_release_at": "2027-03-01T10:00",
            "release_until_offset": "P14D",
            "display_timezone": "UTC",
        },
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/edit"
    ).text
    # datetime-local prefill in session zone (UTC) — value is the
    # ISO datetime without tz.
    assert 'value="2027-03-01T10:00"' in body
    assert 'value="P14D"' in body


def test_edit_inputs_render_without_disabled_attribute(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rw-enabled")
    body = client.get(
        f"/operator/sessions/{review_session.id}/edit"
    ).text
    # No disabled attribute on either input — they're now wired.
    assert (
        'name="responses_release_at" disabled' not in body
    )
    assert (
        'name="release_until_offset" disabled' not in body
    )
