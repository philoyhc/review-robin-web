"""What one page render costs the readiness report (19R Item 5).

`guide/app_responsiveness.md` Finding 6 measured the Validate page
running `validation.validate_session_setup` — all 22 registered rules —
**twice** per render: once for the page's own issue table, and again
inside `views.build_workflow_card_context` for the Workflow card. The
two call sites did not know about each other, and nothing between them
mutates the session, so the second run could only ever reproduce the
first. Rung 1 hands the first run's result to the card.

The ceiling below is deliberately wider than the one page that was
wrong. Every Operations-row page hosts the same card, so any of them
could grow a second run the same way; asserting "at most one run per
render" on all of them is what stops the next one.

This file is about the report's *cost*, never its verdict — which
issues surface is `test_session_validate_page.py` and the rule tests.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.schemas.validation import Severity, ValidationIssue
from app.services import validation
from app.web import views
from ._full_matrix import pin_full_matrix_on_all_instruments


# Every page that renders `operator/partials/next_action_card.html`,
# as a URL suffix on `/operator/sessions/{id}`. Session Home is the
# empty suffix. Extract data is absent on purpose: it is gated on a
# `ready` session, and this fixture stops at `validated` — the state
# Finding 6 measured, and the only one in which the card runs the
# report at all.
CARD_PAGES = ["", "/assignments", "/validate", "/invitations", "/responses"]


def _seed_validated(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """A `validated` session with both rosters imported and every
    instrument pinned to Full Matrix. No assignments generated, so the
    report carries a warning and no errors — enough for `?validated=1`
    to flip the lifecycle."""
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nC,c@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    client.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    db.refresh(review_session)
    assert review_session.status == "validated"
    return review_session


@pytest.fixture()
def report_runs(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Session ids, one per `validate_session_setup` call.

    Both call sites reach the orchestrator through the `validation`
    module object, so patching the attribute there counts the route's
    run and the card builder's alike.
    """
    runs: list[int] = []
    real: Callable[[Session, ReviewSession], list[ValidationIssue]] = (
        validation.validate_session_setup
    )

    def counting(
        db: Session, review_session: ReviewSession
    ) -> list[ValidationIssue]:
        runs.append(review_session.id)
        return real(db, review_session)

    monkeypatch.setattr(validation, "validate_session_setup", counting)
    return runs


def test_the_validate_page_builds_the_readiness_report_once(
    client: TestClient, db: Session, report_runs: list[int]
) -> None:
    review_session = _seed_validated(client, db, code="rc1")
    report_runs.clear()

    response = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    )

    assert response.status_code == 200, response.text
    assert report_runs == [review_session.id]


@pytest.mark.parametrize("suffix", CARD_PAGES)
def test_no_workflow_card_page_builds_the_report_more_than_once(
    client: TestClient, db: Session, report_runs: list[int], suffix: str
) -> None:
    """The ceiling, not the floor: a page is free to run the report
    zero times (the card skips it outside `validated`), but never
    twice for one render."""
    review_session = _seed_validated(client, db, code=f"rc{len(suffix)}x")
    report_runs.clear()

    response = client.get(
        f"/operator/sessions/{review_session.id}{suffix}"
    )

    assert response.status_code == 200, response.text
    assert len(report_runs) <= 1, (
        f"/operator/sessions/{{id}}{suffix} ran the readiness report "
        f"{len(report_runs)} times for one render"
    )


def test_the_card_reports_the_issues_it_was_handed(
    client: TestClient, db: Session
) -> None:
    """The hand-off is load-bearing, not decorative: the summary the
    card renders comes from the passed-in list, so a builder that
    quietly ran its own would show this session's real verdict (clean,
    activatable) instead of the error handed in."""
    review_session = _seed_validated(client, db, code="rc2")
    handed_in = [
        ValidationIssue(
            severity=Severity.error,
            source="test",
            message="Handed in, not recomputed.",
        )
    ]

    ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="validate",
        issues=handed_in,
    )

    summary = ctx["validation_summary"]
    assert summary is not None
    assert summary["error_count"] == 1
    assert summary["can_activate"] is False
    assert ctx["validation_issues_by_severity"]["errors"] == handed_in


def test_every_other_caller_still_builds_its_own_report(
    client: TestClient, db: Session, report_runs: list[int]
) -> None:
    """`issues` defaults to `None`, and the default still runs the
    orchestrator — the hand-off is one route's optimization, not a new
    obligation on the other four pages."""
    review_session = _seed_validated(client, db, code="rc3")
    report_runs.clear()

    views.build_workflow_card_context(
        db, review_session, return_to="assignments"
    )

    assert report_runs == [review_session.id]
