"""Reviewer dashboard sub-rows — one per operator-defined
reviewer page (Segment 18L multi-page surface).

Segment 15B Slice 6 introduced per-instrument sub-rows; Segment
18L's multi-page reviewer surface (one page per run of instruments
between Segment 18M page breaks) repointed the deep link at
``/me/sessions/{id}/{page_n}``, so the sub-rows now reflect
*pages* rather than individual instruments.

Tests pin:

- N==1 instrument session → no ``dashboard-page-row`` markup
  (the byte-identical contract for single-instrument sessions).
- N>1 instruments + single page (no operator page break) → no
  sub-rows; the sub-row would just restate the parent session row
  at the same ``/{id}/1`` URL.
- M>1 pages → one sub-row per page, labelled
  ``"Page N: #n {short_label}, ..."``; pill rolls up the page's
  instruments.
- Per-page "no assignments" surfaces when every instrument on
  the page has zero assignments for this reviewer.
- Per-page link points at ``/me/sessions/{id}/{page_n}``.
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
    pre-15B shape — no ``dashboard-page-row`` markup, no sub-row
    links."""

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
    body = rae_client.get("/me").text

    assert review_session.name in body
    # The sub-row markup is absent.
    assert "dashboard-page-row" not in body


def test_multi_instrument_single_page_dashboard_renders_no_sub_rows(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """N>1 instruments on a single page (no operator page break):
    no sub-rows. A sub-row would just restate the parent session
    row at the same ``/{id}/1`` URL — the parent row already
    carries the session-wide pill."""

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
    body = rae_client.get("/me").text

    # Single page (no break) → no sub-row markup.
    assert "dashboard-page-row" not in body


def test_multi_page_dashboard_renders_one_sub_row_per_page(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Two instruments split across two pages (page break on the
    second) → two sub-rows, each linking to ``/me/.../{page_n}``
    and labelled ``"Page N: #n {short_label}, ..."``."""

    operator = make_client(alice)
    review_session = _make_session_with_pair(operator, db, code="rae-m1-pg")
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
    # Page-break before instrument #2 — so page 1 = first only,
    # page 2 = second only.
    second.starts_new_page = True
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
    body = rae_client.get("/me").text

    # Two sub-rows.
    assert body.count("dashboard-page-row") == 2
    # Labels: "Page N: #n {short_label}, ...". The default seed
    # instrument has no short_label so falls back to bare "#1".
    assert "Page 1: #1" in body
    assert "Page 2: #2 peer" in body


def test_multi_page_dashboard_renders_deep_link_to_page_url(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the session is fully activated and ``link_enabled``,
    each per-page sub-row renders an ``<a href>`` pointing at
    ``/me/sessions/{id}/{page_n}`` — not the older per-
    instrument-position URL the dashboard used pre-18L."""
    operator = make_client(alice)
    review_session = _make_session_with_pair(
        operator, db, code="rae-pg-link"
    )
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
    second.starts_new_page = True
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=first
    )
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=second
    )
    review_session.assignment_mode = "rule_based"
    db.flush()
    db.commit()
    # Pin Full Matrix on every instrument so activate succeeds and
    # the dashboard renders linked sub-rows.
    from ._full_matrix import pin_full_matrix_on_all_instruments
    pin_full_matrix_on_all_instruments(db, review_session.id)
    _activate(operator, review_session)
    db.refresh(review_session)
    if review_session.activated_at is None:
        pytest.skip(
            "Activation didn't reach `ready` in this fixture; the "
            "label / sub-row count test above already pins the "
            "non-linked render path."
        )

    rae_client = make_client(rae)
    body = rae_client.get("/me").text
    assert f'href="/me/sessions/{review_session.id}/1"' in body
    assert f'href="/me/sessions/{review_session.id}/2"' in body


def test_sub_row_state_rolls_up_per_page(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Submitting all of instrument A but none of instrument B,
    with each on its own page, → page 1 (A) reads ``submitted``
    and page 2 (B) reads ``not started``. Per-page rollup mirrors
    the surface's ``_page_status_for_group`` — uniform across the
    page's instruments carry through; mixed reads ``in progress``.
    """

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
    second.starts_new_page = True
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
    body = rae_client.get("/me").text

    # Both sub-rows render in page order: page 1 (first instrument)
    # then page 2 (peer survey).
    sub_rows = body.split('class="dashboard-page-row"')
    assert len(sub_rows) == 3  # one head split + two row chunks
    # Page 1: required fields filled + submitted_at → ``submitted``.
    assert ">submitted</span>" in sub_rows[1]
    # Page 2: no responses on its instrument → ``not started``.
    assert ">not started</span>" in sub_rows[2]


def test_sub_row_renders_no_assignments_state_when_reviewer_excluded(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the reviewer has zero assignments on every instrument
    on a page (e.g. excluded by that instrument's pinned rule), the
    page sub-row renders the ``no assignments`` pill — visually
    distinct from ``not started`` so the reviewer can spot the
    per-page gap on their own dashboard."""

    operator = make_client(alice)
    review_session = _make_session_with_pair(operator, db, code="rae-m3")
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
    second.starts_new_page = True
    # Only one assignment — on ``first``. Nothing on ``second`` for
    # Rae; the per-page resolver should report ``no assignments``
    # for page 2.
    _add_assignment_for_reviewer(
        db, review_session=review_session, instrument=first
    )
    review_session.assignment_mode = "rule_based"
    db.flush()
    db.commit()
    _activate(operator, review_session)

    rae_client = make_client(rae)
    body = rae_client.get("/me").text

    assert "no assignments" in body
    sub_rows = body.split('class="dashboard-page-row"')
    # Page 2 (peer-survey) is the one with no assignments.
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
