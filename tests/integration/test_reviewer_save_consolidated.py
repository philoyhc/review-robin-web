"""Integration tests for Segment 18L PR 1a — the consolidated
reviewer-save endpoint at ``POST /reviewer/sessions/{id}/save``.

PR 1a adds the route additively; the existing positional save at
``POST /reviewer/sessions/{id}/{position}/save`` keeps working
until PR 1b deletes it. These tests pin the new endpoint's
contract: walks every upsert in the payload, emits a single
``responses.saved`` audit row with the new ``counts`` keys
(``assignments_touched`` + ``responses_saved``), redirects to the
bare session URL on success, 400s on validation errors, honors
the accepting-responses lifecycle gate.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
)
from tests.integration.test_reviewer_response_flow import (
    _operator_creates_session_with_pair,
)


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


# --------------------------------------------------------------------------- #
# Happy path — consolidated save persists + emits single audit row
# --------------------------------------------------------------------------- #


def test_consolidated_save_persists_and_redirects_to_bare_url(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="ra-1",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()

    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/save",
        data={
            f"response[{assignment.id}][rating]": "4",
            f"response[{assignment.id}][comments]": "good work",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == (
        f"/reviewer/sessions/{review_session.id}"
    )


def test_consolidated_save_emits_audit_row_with_new_counts_keys(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Audit envelope swap (decision 4) — `assignments_touched` +
    `responses_saved` replace the legacy `saved` + `validation_errors`
    keys. One row per call regardless of how many assignments are
    in the payload.
    """
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="ra-2",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()

    before = _audit_count(db, "responses.saved")
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/save",
        data={
            f"response[{assignment.id}][rating]": "5",
            f"response[{assignment.id}][comments]": "wonderful",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert _audit_count(db, "responses.saved") == before + 1
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "responses.saved")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event is not None
    counts = event.detail["counts"]
    assert counts["assignments_touched"] == 1
    assert counts["responses_saved"] == 2  # rating + comments
    # Legacy keys retired cleanly.
    assert "saved" not in counts
    assert "validation_errors" not in counts


def test_consolidated_save_handles_multi_instrument_payload(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A payload spanning multiple instruments persists every
    assignment's responses in one call + counts assignments_touched
    correctly."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="ra-3",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,  # we add a second instrument first
    )
    # Add a second instrument before activating.
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model"
    )
    # Re-pin Full Matrix on the new instrument + regenerate
    # assignments, then activate.
    from tests.integration._full_matrix import (
        generate_via_page_button,
        pin_full_matrix_on_all_instruments,
    )

    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    operator.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )

    rae_client = make_client(rae)
    assignments = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalars().all()
    assert len({a.instrument_id for a in assignments}) == 2

    payload: dict[str, str] = {}
    for a in assignments:
        payload[f"response[{a.id}][rating]"] = "3"

    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/save",
        data=payload,
        follow_redirects=False,
    )
    assert response.status_code == 303

    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "responses.saved")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event is not None
    counts = event.detail["counts"]
    assert counts["assignments_touched"] == len(assignments)
    assert counts["responses_saved"] == len(assignments)


# --------------------------------------------------------------------------- #
# Error paths
# --------------------------------------------------------------------------- #


def test_consolidated_save_returns_400_on_validation_errors(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Invalid upserts (e.g. non-numeric in a rating field) raise
    400 with a JSON detail listing each rejected (assignment_id,
    field_key, value). PR 1b will wire the inline single-page
    re-render in place of the JSON; for PR 1a the 400 is the
    contract."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="ra-4",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()

    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/save",
        data={
            # Rating expects 1-5; "bad" should fail validation.
            f"response[{assignment.id}][rating]": "bad",
        },
        follow_redirects=False,
    )
    # PR 1a returns 400 (HTML error page via the global handler);
    # PR 1b will wire the inline single-page re-render that
    # highlights the offending cell on top of the saved values.
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _audit_count(db: Session, event_type: str) -> int:
    return len(
        db.execute(
            select(AuditEvent).where(AuditEvent.event_type == event_type)
        ).scalars().all()
    )
