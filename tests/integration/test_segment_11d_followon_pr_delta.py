"""PR δ — Reviewer surface client-side page navigation + dirty
preservation.

Per `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on: Reviewer
surface — multi-instrument rewrite" → PR δ. Every instrument group
the reviewer is assigned on lives in the DOM at once; CSS hides the
non-active ones. Page #N click is JS-driven (toggles ``.rs-active``,
``pushState``s the URL); dirty edits in hidden groups survive
navigation; Discard is JS-only and restores from
``data-rs-saved-value`` baselines; Submit reads inputs from every
group.

The JS itself is not tractable from pytest. These tests pin the
server-rendered scaffold the JS depends on and the route-level
invariants (Save still filters by position; Submit reads every
input across every group).
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
    Instrument,
    Response,
    ReviewSession,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)
from app.services import instruments as instruments_service


def _setup_two_instrument_session(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str = "rae@example.edu",
    reviewee_ident: str = "carol@example.edu",
) -> tuple[ReviewSession, Instrument, Instrument]:
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
                f"RevieweeName,RevieweeEmail\nCarol,{reviewee_ident}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    [first] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(first.id)},
        follow_redirects=False,
    )
    second = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != first.id)
    ).scalar_one()
    # ``instruments/add`` clones full-matrix assignments onto the new
    # instrument automatically (per ``create_instrument``), so no
    # manual Assignment seeding is needed.
    instruments_service.update_short_label(
        db, instrument=first, short_label="Self-eval", actor=None
    )
    instruments_service.update_short_label(
        db, instrument=second, short_label="Peer review", actor=None
    )
    operator_client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
    operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)
    db.refresh(first)
    db.refresh(second)
    assert review_session.status == "ready"
    return review_session, first, second


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


# ── Markup scaffold ──────────────────────────────────────────────────────


def test_inputs_carry_data_rs_saved_value(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Every input/textarea/select on the surface carries
    ``data-rs-saved-value`` so Discard's JS handler can restore the
    last-saved baseline. On a fresh session every saved value is
    empty so the attribute renders as ``data-rs-saved-value=""`` —
    the existence of the attribute matters, not its content."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator, db, code="rae-d-savedval"
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    # At least one input carries the attribute.
    assert "data-rs-saved-value=" in body


# ── Save filter still narrows by position (PR γ behaviour) ───────────────


def test_save_still_filters_cross_page_inputs_under_pr_delta(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Submit's POST body carries every instrument's inputs because the
    surface renders all instruments on the page. The per-page Save
    filter must still drop cross-page inputs so Save's scope stays
    "this page only".

    Migrated for Segment 18L PR 1d: a single-page-default session
    places every instrument on the same page, so we set a page break
    after the first instrument to carve out two pages."""
    operator = make_client(alice)
    review_session, first, second = _setup_two_instrument_session(
        operator, db, code="rae-d-save-filter"
    )
    instruments_service.create_page_break_after(db, instrument=first)
    page1_assignment = db.execute(
        select(Assignment)
        .where(Assignment.session_id == review_session.id)
        .where(Assignment.instrument_id == first.id)
    ).scalar_one()
    page2_assignment = db.execute(
        select(Assignment)
        .where(Assignment.session_id == review_session.id)
        .where(Assignment.instrument_id == second.id)
    ).scalar_one()

    rae_client = make_client(rae)
    rae_client.post(
        f"/me/sessions/{review_session.id}/1/save",
        data={
            f"response[{page1_assignment.id}][comments]": "page-1 saved",
            f"response[{page2_assignment.id}][comments]": "page-2 dirty",
        },
        follow_redirects=False,
    )
    page1_responses = (
        db.execute(
            select(Response).where(Response.assignment_id == page1_assignment.id)
        )
        .scalars()
        .all()
    )
    page2_responses = (
        db.execute(
            select(Response).where(Response.assignment_id == page2_assignment.id)
        )
        .scalars()
        .all()
    )
    assert any(r.value == "page-1 saved" for r in page1_responses)
    assert not any(r.value == "page-2 dirty" for r in page2_responses)


# ── Submit reads every input across every group ──────────────────────────


def test_submit_persists_inputs_from_every_group(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Submit's scope is session-wide, so it must read values from
    every instrument group's inputs (not just the active page).
    Under PR δ the form body now naturally carries every group's
    inputs because every group lives in the DOM. Submit blocks here
    because the seeded ``rating`` field is required and not provided,
    but the draft writes still commit ahead of the missing-required
    block — so both pages' typed values land in the DB."""
    operator = make_client(alice)
    review_session, first, second = _setup_two_instrument_session(
        operator, db, code="rae-d-submit-all"
    )
    page1_assignment = db.execute(
        select(Assignment)
        .where(Assignment.session_id == review_session.id)
        .where(Assignment.instrument_id == first.id)
    ).scalar_one()
    page2_assignment = db.execute(
        select(Assignment)
        .where(Assignment.session_id == review_session.id)
        .where(Assignment.instrument_id == second.id)
    ).scalar_one()

    rae_client = make_client(rae)
    rae_client.post(
        f"/me/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][comments]": "page-1 submit",
            f"response[{page2_assignment.id}][comments]": "page-2 submit",
        },
        follow_redirects=False,
    )
    page1_responses = (
        db.execute(
            select(Response).where(Response.assignment_id == page1_assignment.id)
        )
        .scalars()
        .all()
    )
    page2_responses = (
        db.execute(
            select(Response).where(Response.assignment_id == page2_assignment.id)
        )
        .scalars()
        .all()
    )
    # Both pages' values land in the DB after Submit.
    assert any(r.value == "page-1 submit" for r in page1_responses)
    assert any(r.value == "page-2 submit" for r in page2_responses)


