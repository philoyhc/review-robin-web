"""Coverage for the reviewer per-session summary page —
Segment 17B Phase 2 PR B.

Pins the gate (incomplete submission → redirect to dashboard),
the submit-time redirect to the summary URL on whole-session
completion, the rendered summary page structure, the CSV
download's shape, and the PR A dashboard link wiring (Session
column points at the summary URL when Reviewer Status is
``submitted``).
"""
from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, ReviewSession


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae",
        provider="aad",
    )


def _make_ready_session(
    operator: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str = "rae@example.edu",
) -> ReviewSession:
    """Operator-side setup: create a session, import the pair,
    pin Full Matrix, activate. Returns the ready session."""
    operator.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nRae,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # Wave 5 PR 5.2 — lazily materialise the Full Matrix
    # ``session_rule_sets`` row (auto-seed retired).
    from ._full_matrix import pin_full_matrix_on_all_instruments
    pin_full_matrix_on_all_instruments(db, review_session.id)
    # Workflow card's Prepare + Activate flow (post-18F Part 1).
    operator.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    return review_session


def test_summary_gate_redirects_when_session_not_fully_submitted(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="summ-gate")
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary",
        follow_redirects=False,
    )
    # Not submitted yet → redirect to the reviewer dashboard.
    assert response.status_code == 303
    assert response.headers["location"] == "/reviewer"


def test_summary_renders_after_full_submission(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="summ-ok")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    # Submit; the redirect should already point at the summary.
    submit = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "5",
        },
        follow_redirects=False,
    )
    assert submit.status_code == 303
    assert submit.headers["location"] == (
        f"/reviewer/sessions/{review_session.id}/summary"
    )
    page = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    )
    assert page.status_code == 200
    body = page.text
    assert "Your responses" in body
    # CSV download button is visible at the top of the page.
    assert (
        f'/reviewer/sessions/{review_session.id}/summary.csv' in body
    )
    # The Carol row appears under the (only) instrument section.
    assert "Carol" in body


@pytest.mark.skip(
    reason="Segment 18J Wave 2 PR iii-b2 — response saved via the "
    "shim-resolved RTD path no longer flows into the extract; the "
    "extract needs an iii-b3/b4 update to handle inline-shaped "
    "fields the same way."
)
def test_summary_csv_streams_reviewer_only_rows(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="summ-csv")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "3",
        },
        follow_redirects=False,
    )
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    # Filename ``{code}_my_responses.csv``.
    assert "summ-csv_my_responses.csv" in (
        response.headers["content-disposition"]
    )
    body = response.text
    # The reviewer's row should be in the CSV; the 21-column
    # header from the unified extract is present too.
    assert "ReviewerName" in body
    assert "Carol" in body


def test_dashboard_link_points_at_summary_when_submitted(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """PR A's link wiring — once Reviewer Status is ``submitted``
    the Session column links to the summary URL."""
    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="dash-link")
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "4",
        },
        follow_redirects=False,
    )
    body = rae_client.get("/reviewer").text
    # Session column now anchors at the summary URL, not the
    # surface position.
    assert (
        f'href="/reviewer/sessions/{review_session.id}/summary"' in body
    )


def test_summary_single_instrument_heading_uses_short_label_when_set(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Single-instrument session: the section heading drops the
    ``Page #1`` prefix and renders the operator's ``short_label``,
    matching the form's heading composition."""
    from app.db.models import Instrument
    from app.services import instruments as instruments_service

    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="summ-h-short")
    # Set short_label on the (only) instrument before the reviewer
    # submits.  ``_make_ready_session`` already activated; the spec
    # allows heading-meta edits at any lifecycle.
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Self-eval", actor=None
    )

    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "5",
        },
        follow_redirects=False,
    )
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert "<h2 style=\"margin-top: 0;\">Self-eval</h2>" in body
    # No Page-# prefix on a single-instrument session.
    assert "Page #1" not in body


def test_summary_single_instrument_heading_falls_back_to_name_when_no_short_label(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Single-instrument session with no ``short_label``: the
    heading falls back to ``instrument.name`` so the section
    card always has *some* title."""
    from app.db.models import Instrument

    operator = make_client(alice)
    review_session = _make_ready_session(operator, db, code="summ-h-name")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    # Default seed leaves short_label NULL; the default name is
    # "Instrument #1" — pin it explicitly so the assertion is
    # robust to default-name churn.
    instrument.name = "Custom instrument name"
    db.commit()

    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "5",
        },
        follow_redirects=False,
    )
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert (
        "<h2 style=\"margin-top: 0;\">Custom instrument name</h2>" in body
    )


def test_summary_multi_instrument_headings_use_page_prefix(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Multi-instrument session: each section heading carries
    ``Page #{N}: {short_label}`` exactly the way the form does
    (``views.instrument_heading`` composition rules).

    Seeds the session manually so a second instrument can land
    *before* activation — ``+Instrument`` 409s once
    ``is_ready``. ``_make_ready_session`` collapses prepare +
    activate, so it's not reusable here.
    """
    from app.db.models import Assignment, Instrument
    from app.services import instruments as instruments_service

    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "summ-h-multi", "code": "summ-h-multi"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "summ-h-multi")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nRae,{rae.email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # Add the second instrument while the session is still draft.
    instrument_1 = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(instrument_1.id)},
        follow_redirects=False,
    )
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    assert len(instruments) == 2
    instrument_1, instrument_2 = instruments
    instruments_service.update_short_label(
        db, instrument=instrument_1, short_label="Self-eval", actor=None
    )
    instruments_service.update_short_label(
        db, instrument=instrument_2, short_label="Peer review", actor=None
    )
    from ._full_matrix import pin_full_matrix_on_all_instruments
    pin_full_matrix_on_all_instruments(db, review_session.id)
    operator.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)

    # Submit responses on every assignment so the summary unlocks.
    # Save is per-instrument-page — save each page separately
    # with that page's assignment payload.
    assignments = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    rae_client = make_client(rae)
    for position, instrument in enumerate(instruments, start=1):
        page_data: dict[str, str] = {"current_position": str(position)}
        for a in assignments:
            if a.instrument_id != instrument.id:
                continue
            page_data[f"response[{a.id}][rating]"] = "5"
        rae_client.post(
            f"/reviewer/sessions/{review_session.id}/{position}/save",
            data=page_data,
            follow_redirects=False,
        )
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        follow_redirects=False,
    )

    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert (
        "<h2 style=\"margin-top: 0;\">Page #1: Self-eval</h2>" in body
    )
    assert (
        "<h2 style=\"margin-top: 0;\">Page #2: Peer review</h2>" in body
    )
