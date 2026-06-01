"""Reviewer dashboard lobby — 17B Phase 2 lobby expansion + two-
status columns. The per-page sub-row treatment (Segment 15B
Slice 6 + Segment 18L) retired 2026-06-01 — the participant
lobby now reads the main session row only, with multi-page
sessions linked through to the surface's own pager rather than
deep-linked from the lobby. The tests below cover what's left:
the 5-column header + lifecycle pill rendering.
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
    Reviewee,
    Reviewer,
    ReviewSession,
)


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _make_session_with_pair(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str = "rae@example.edu",
    reviewee_ident: str = "carol@example.edu",
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
                f"RevieweeName,RevieweeEmail\nCarol,{reviewee_ident}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    return review_session



def _add_assignment_for_reviewer(
    db: Session,
    *,
    review_session: ReviewSession,
    instrument: Instrument,
) -> Assignment:
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalar_one()
    a = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
    )
    db.add(a)
    db.flush()
    return a


def _activate(operator_client: TestClient, review_session: ReviewSession) -> None:
    """Force-set assignment_mode + transition session through
    validate → active so the reviewer dashboard treats it as live."""
    operator_client.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )



# --------------------------------------------------------------------------- #
# 17B Phase 2 PR A — lobby expansion + two-status columns
# --------------------------------------------------------------------------- #


def test_lobby_renders_five_column_header(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer lobby (post-17B-Phase-2-PRA) carries five
    columns: Session, Start, End, Session status, Reviewer status."""
    operator = make_client(alice)
    review_session = _make_session_with_pair(operator, db, code="lobby-cols")
    [instrument] = list(
        db.execute(select(Instrument).where(Instrument.session_id == review_session.id)).scalars()
    )
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=instrument
    )
    rae_client = make_client(rae)
    body = rae_client.get("/me").text
    assert "<th>Session</th>" in body
    assert "<th>Start</th>" in body
    assert "<th>End</th>" in body
    assert "<th>Session status</th>" in body
    assert "<th>Reviewer status</th>" in body


def test_lobby_pre_ready_session_renders_not_opened_unlinked(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A session the reviewer is rostered on but that hasn't been
    activated yet renders ``not opened`` + unlinked session name +
    blank Start cell."""
    operator = make_client(alice)
    review_session = _make_session_with_pair(operator, db, code="lobby-preopen")
    [instrument] = list(
        db.execute(select(Instrument).where(Instrument.session_id == review_session.id)).scalars()
    )
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=instrument
    )
    rae_client = make_client(rae)
    body = rae_client.get("/me").text
    assert ">not opened</span>" in body
    # The Session column should not link the session name when the
    # session isn't opened — the row carries the name as plain text.
    assert (
        f'<a href="/me/sessions/{review_session.id}/1">'
        not in body
    )


def test_lobby_ready_session_renders_open_and_start_stamp(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A fully-activated session renders ``open`` + linked session
    name + a Start stamp (sourced from ``activated_at``)."""
    operator = make_client(alice)
    review_session = _make_session_with_pair(operator, db, code="lobby-open")
    [instrument] = list(
        db.execute(select(Instrument).where(Instrument.session_id == review_session.id)).scalars()
    )
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=instrument
    )
    # Pin a rule + activate so the session reaches ``ready``.
    # Wave 5 PR 5.2 — lazily materialise the Full Matrix
    # ``session_rule_sets`` row (auto-seed retired).
    from ._full_matrix import pin_full_matrix_on_all_instruments
    pin_full_matrix_on_all_instruments(db, review_session.id)
    _activate(operator, review_session)
    db.refresh(review_session)

    rae_client = make_client(rae)
    body = rae_client.get("/me").text
    assert ">open</span>" in body
    assert (
        f'<a href="/me/sessions/{review_session.id}/1">' in body
    )
    # ``activated_at`` is stamped on the first activation.
    assert review_session.activated_at is not None
