"""Slice 6 coverage for the reviewer dashboard per-instrument
grouping.

Single-instrument sessions render byte-identical to their pre-15B
shape (invariant #3 from the segment plan). Multi-instrument
sessions grow stacked sub-rows — one per instrument — each with
its own progress pill computed from
``responses.reviewer_session_state_per_instrument``.

Tests pin:

- N==1 session → no ``dashboard-instrument-row`` markup (the
  byte-identical contract for single-instrument sessions).
- N>1 session → one sub-row per instrument; pills reflect the
  per-instrument state independently.
- Per-instrument "no assignments" state surfaces when the
  reviewer is excluded from an instrument by its pinned rule.
- Per-instrument link points at the correct
  ``/reviewer/sessions/{id}/{position}`` URL (the same 1-based
  position the reviewer surface uses).
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
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import instruments as instruments_service


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


def _add_instrument(
    db: Session,
    *,
    review_session: ReviewSession,
    name: str,
    short_label: str | None = None,
) -> Instrument:
    instrument = Instrument(
        session_id=review_session.id,
        name=name,
        short_label=short_label,
        order=99,
    )
    db.add(instrument)
    db.flush()
    return instrument


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


def test_single_instrument_dashboard_renders_no_sub_rows(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """N==1 session: dashboard renders byte-identical to its
    pre-15B shape — no ``dashboard-instrument-row`` markup, no
    sub-row links."""

    operator = make_client(alice)
    review_session = _make_session_with_pair(operator, db, code="rae-s1")
    [instrument] = list(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars()
    )
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=instrument
    )
    review_session.assignment_mode = "rule_based"
    db.flush()
    db.commit()
    _activate(operator, review_session)

    rae_client = make_client(rae)
    body = rae_client.get("/reviewer").text

    assert review_session.name in body
    # The per-instrument sub-row markup is absent.
    assert "dashboard-instrument-row" not in body


def test_multi_instrument_dashboard_renders_one_sub_row_per_instrument(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """N>1 session: one ``dashboard-instrument-row`` per instrument,
    each with its own pill + a deep link to the per-position
    surface URL."""

    operator = make_client(alice)
    review_session = _make_session_with_pair(operator, db, code="rae-m1")
    [first] = list(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars()
    )
    second = _add_instrument(
        db,
        review_session=review_session,
        name="Peer survey",
        short_label="peer",
    )
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=first
    )
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=second
    )
    review_session.assignment_mode = "rule_based"
    db.flush()
    db.commit()
    _activate(operator, review_session)

    rae_client = make_client(rae)
    body = rae_client.get("/reviewer").text

    assert body.count("dashboard-instrument-row") == 2
    # The peer-survey sub-row carries its label; per 17B Phase 2 PR A
    # the deep link only renders when the parent session is at least
    # ``open`` (this fixture force-marks ``validated`` without a
    # clean activation so the link is absent), but the label and
    # row markup still appear.
    assert "peer" in body


def test_sub_row_state_pulls_from_per_instrument_projection(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Submitting on instrument A but not B → A's sub-row shows
    ``submitted`` while B's shows ``not started``. The session-
    level pill rolls up to ``in progress`` per the existing
    aggregate logic; the per-instrument breakdown lets the reviewer
    see which instrument needs work."""

    operator = make_client(alice)
    review_session = _make_session_with_pair(operator, db, code="rae-m2")
    [first] = list(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars()
    )
    second = _add_instrument(
        db,
        review_session=review_session,
        name="Peer survey",
        short_label="peer",
    )
    # Make sure each instrument has a response field so "submitted"
    # has a meaning beyond "any row exists".
    instruments_service.ensure_default_response_type_definitions(
        db, review_session
    )
    from app.services.instruments import (
        DEFAULT_INSTRUMENT_NAME,  # noqa: F401
    )
    from datetime import datetime, timezone

    a_first = _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=first
    )
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=second
    )
    db.refresh(first)
    field_first = first.response_fields[0]
    db.add(
        Response(
            assignment_id=a_first.id,
            response_field_id=field_first.id,
            value="5",
            submitted_at=datetime.now(timezone.utc),
        )
    )
    review_session.assignment_mode = "rule_based"
    db.flush()
    db.commit()
    _activate(operator, review_session)

    rae_client = make_client(rae)
    body = rae_client.get("/reviewer").text

    # Both sub-rows render. Order: first instrument (rule_based seed
    # default instrument) then "Peer survey".
    sub_rows = body.split('class="dashboard-instrument-row"')
    assert len(sub_rows) == 3  # one head split + two row chunks
    # First instrument: required fields filled + submitted_at →
    # ``submitted`` pill.
    assert ">submitted</span>" in sub_rows[1]
    # Second instrument (peer): no responses → ``not started``.
    assert ">not started</span>" in sub_rows[2]


def test_sub_row_renders_no_assignments_state_when_reviewer_excluded(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the reviewer has zero assignments on one of the
    session's instruments (e.g. excluded by that instrument's
    pinned rule), the sub-row renders the ``no assignments`` pill
    — visually distinct from ``not started`` so the operator can
    spot the per-instrument gap on the reviewer's own dashboard."""

    operator = make_client(alice)
    review_session = _make_session_with_pair(operator, db, code="rae-m3")
    [first] = list(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars()
    )
    _add_instrument(
        db,
        review_session=review_session,
        name="Peer survey",
        short_label="peer",
    )
    # Only one assignment — on ``first``. Nothing on ``second`` for
    # Rae; the per-instrument resolver should report
    # ``no assignments`` for the second sub-row.
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=first
    )
    review_session.assignment_mode = "rule_based"
    db.flush()
    db.commit()
    _activate(operator, review_session)

    rae_client = make_client(rae)
    body = rae_client.get("/reviewer").text

    assert "no assignments" in body
    # The sub-row that carries the ``no assignments`` pill is the
    # peer-survey one (the second instrument).
    sub_rows = body.split('class="dashboard-instrument-row"')
    assert ">no assignments</span>" in sub_rows[2]
    # The ``(N/M)`` muted suffix is suppressed on no-assignments
    # rows — there's no useful count to show.
    assert "(0/0)" not in sub_rows[2]


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
    body = rae_client.get("/reviewer").text
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
    body = rae_client.get("/reviewer").text
    assert ">not opened</span>" in body
    # The Session column should not link the session name when the
    # session isn't opened — the row carries the name as plain text.
    assert (
        f'<a href="/reviewer/sessions/{review_session.id}/1">'
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
    body = rae_client.get("/reviewer").text
    assert ">open</span>" in body
    assert (
        f'<a href="/reviewer/sessions/{review_session.id}/1">' in body
    )
    # ``activated_at`` is stamped on the first activation.
    assert review_session.activated_at is not None
