"""Route + helper coverage for the four-datetime schedule
ordering chain on Session Edit Details and Create New Session.

Order:
    scheduled_activate_at ≤ deadline ≤ responses_release_at <
    responses_release_until

The four per-field parsers handle parse + intra-field rules
(lead-time floors, magnitude caps, ``until > at``). The shared
``scheduled_events.validate_schedule_ordering`` handles the two
inter-field pairs the parsers don't cover
(``End ≥ Start``, ``Release-from ≥ End``); the routes call it
right after the individual parsers and translate the raised
:class:`ScheduledActivateError` to HTTP 422. Pairs with either
side ``None`` skip silently.

The client-side ``min`` / ``max`` attributes on the four
``datetime-local`` inputs make the picker block invalid choices
at the operator's keyboard / fingertip — but the server stays
the load-bearing safety net, which is what these tests pin.
"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services.scheduled_events import (
    ScheduledActivateError,
    validate_schedule_ordering,
)


# ── Helper-direct unit ─────────────────────────────────────────────────

import datetime as _dt
from datetime import timezone


def _ts(year: int, month: int, day: int, hour: int = 0) -> _dt.datetime:
    return _dt.datetime(year, month, day, hour, tzinfo=timezone.utc)


def test_validate_schedule_ordering_accepts_chain_in_order() -> None:
    validate_schedule_ordering(
        scheduled_activate_at=_ts(2027, 1, 1),
        deadline=_ts(2027, 1, 10),
        responses_release_at=_ts(2027, 1, 10),
    )


def test_validate_schedule_ordering_skips_pairs_with_null() -> None:
    """Each pair is checked only when both members are set —
    one side ``None`` means the pair carries no constraint."""
    # Start NULL: Start-End pair skipped; End-Release-from still
    # checked and (in-order) passes.
    validate_schedule_ordering(
        scheduled_activate_at=None,
        deadline=_ts(2027, 1, 1),
        responses_release_at=_ts(2027, 1, 10),
    )
    # End NULL: both pairs skip (each touches End).
    validate_schedule_ordering(
        scheduled_activate_at=_ts(2027, 1, 10),
        deadline=None,
        responses_release_at=_ts(2027, 1, 5),
    )
    # Release-from NULL: Start-End checked (in order, passes);
    # End-Release-from pair skipped.
    validate_schedule_ordering(
        scheduled_activate_at=_ts(2027, 1, 1),
        deadline=_ts(2027, 1, 10),
        responses_release_at=None,
    )


def test_validate_schedule_ordering_rejects_end_before_start() -> None:
    with pytest.raises(ScheduledActivateError, match="End must be on or after Start"):
        validate_schedule_ordering(
            scheduled_activate_at=_ts(2027, 1, 10),
            deadline=_ts(2027, 1, 1),
            responses_release_at=None,
        )


def test_validate_schedule_ordering_rejects_release_before_end() -> None:
    with pytest.raises(
        ScheduledActivateError,
        match="Release responses from must be on or after End",
    ):
        validate_schedule_ordering(
            scheduled_activate_at=None,
            deadline=_ts(2027, 1, 10),
            responses_release_at=_ts(2027, 1, 5),
        )


def test_validate_schedule_ordering_emits_start_end_first_when_both_violate() -> None:
    """Start vs End is checked first; the operator sees the
    upstream-most error before any downstream one."""
    with pytest.raises(ScheduledActivateError, match="End must be on or after Start"):
        validate_schedule_ordering(
            scheduled_activate_at=_ts(2027, 1, 10),
            deadline=_ts(2027, 1, 1),
            responses_release_at=_ts(2026, 12, 1),
        )


# ── Route-level — Edit + Create ────────────────────────────────────────


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
) -> tuple[int, str]:
    data: dict[str, str] = {
        "name": review_session.name,
        "code": review_session.code,
        "description": review_session.description or "",
        "display_timezone": "UTC",
    }
    data.update(overrides)
    response = client.post(
        f"/operator/sessions/{review_session.id}/edit",
        data=data,
        follow_redirects=False,
    )
    return response.status_code, response.text


def test_create_rejects_end_before_start(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "ord-end-before-start",
            "description": "",
            "scheduled_activate_at": "2027-02-01T09:00",
            "deadline": "2027-01-01T09:00",
            "display_timezone": "UTC",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "End must be on or after Start" in response.text


def test_create_rejects_release_before_end(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={
            "name": "S",
            "code": "ord-rel-before-end",
            "description": "",
            "deadline": "2027-02-01T09:00",
            "responses_release_at": "2027-01-15T09:00",
            "display_timezone": "UTC",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "Release responses from must be on or after End" in response.text


def test_edit_rejects_end_before_start(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-edit-start")
    status_code, body = _submit_edit(
        client,
        review_session,
        scheduled_activate_at="2027-02-01T09:00",
        deadline="2027-01-01T09:00",
    )
    assert status_code == 422
    assert "End must be on or after Start" in body


def test_edit_rejects_release_before_end(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-edit-rel")
    status_code, body = _submit_edit(
        client,
        review_session,
        deadline="2027-02-01T09:00",
        responses_release_at="2027-01-15T09:00",
    )
    assert status_code == 422
    assert "Release responses from must be on or after End" in body


def test_edit_accepts_chain_in_order(
    client: TestClient, db: Session
) -> None:
    """Positive control — a fully-ordered chain saves cleanly."""
    review_session = _make_session(client, db, code="ord-good-chain")
    status_code, _body = _submit_edit(
        client,
        review_session,
        scheduled_activate_at="2027-01-01T09:00",
        deadline="2027-01-15T09:00",
        responses_release_at="2027-01-20T09:00",
        responses_release_until="2027-01-30T09:00",
    )
    assert status_code == 303


# ── Client-side: min / max attributes on the inputs ────────────────────


def test_edit_form_renders_min_max_on_dependent_inputs(
    client: TestClient, db: Session
) -> None:
    """The Edit GET render carries the ordering bounds as
    ``min`` / ``max`` so the browser picker blocks invalid
    choices at keyboard / picker time."""
    review_session = _make_session(
        client,
        db,
        code="ord-bounds",
        data={
            "scheduled_activate_at": "2027-01-01T09:00",
            "deadline": "2027-01-15T09:00",
            "responses_release_at": "2027-01-20T09:00",
            "responses_release_until": "2027-01-30T09:00",
            "display_timezone": "UTC",
        },
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/edit"
    ).text
    # Start's max is End.
    assert 'name="scheduled_activate_at"' in body
    assert (
        'name="scheduled_activate_at"\n                     value="2027-01-01T09:00"\n                     max="2027-01-15T09:00"'
        in body
    )
    # End's min is Start; max is Release-from.
    assert 'min="2027-01-01T09:00"' in body
    assert 'max="2027-01-20T09:00"' in body
    # Release-until's min is Release-from.
    assert 'min="2027-01-20T09:00"' in body


def test_new_session_form_includes_live_update_script(
    client: TestClient, db: Session
) -> None:
    """The Create New Session form has no prefill; the
    ``min``/``max`` attributes start absent. The live-update
    script wires them up as the operator types."""
    body = client.get("/operator/sessions/new").text
    # The shared partial's distinctive IDS array is the cheapest
    # marker that the script is on the page.
    assert (
        'IDS = [\n      "scheduled_activate_at",\n      "deadline",\n      "responses_release_at",\n      "responses_release_until",\n    ]'
        in body
    )
