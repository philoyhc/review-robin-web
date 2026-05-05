"""PR ε — Acknowledge missing required (session-wide) + preview adaptation.

Per `guide/segment_11D_v2_sweep_non_session.md` "Follow-on: Reviewer
surface — multi-instrument rewrite" → PR ε.

- ``responses.submit`` already validates required fields session-wide;
  PR ε adds a ``position`` field on ``MissingPosition`` so the banner
  can tell the reviewer which page to navigate to.
- Operator preview's unified action row collapses to just Page #N
  buttons (Save / Discard / divider / Submit suppressed). The status
  panel renders without per-page pills; inputs render disabled, as
  today.
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
    ReviewSession,
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
    operator_client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    [first] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/instruments/add",
        data={"after": str(first.id)},
        follow_redirects=False,
    )
    second = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != first.id)
    ).scalar_one()
    seed_assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    db.add(
        Assignment(
            session_id=review_session.id,
            reviewer_id=seed_assignment.reviewer_id,
            reviewee_id=seed_assignment.reviewee_id,
            instrument_id=second.id,
            include=True,
            created_by_mode="full_matrix",
        )
    )
    db.commit()
    instruments_service.update_short_label(
        db, instrument=first, short_label="Self-eval", actor=None
    )
    instruments_service.update_short_label(
        db, instrument=second, short_label="Peer review", actor=None
    )
    operator_client.get(f"/operator/sessions/{review_session.id}?validated=1")
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


# ── MissingPosition.position is populated session-wide ───────────────────


def test_submit_missing_carries_page_number_for_each_gap(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Submit with required gaps on Page 1 *and* Page 2 returns a
    ``MissingPosition`` per gap, each carrying the page number the
    reviewer needs to navigate to. Sort order is (position, name,
    field) so the banner reads top-to-bottom in walk order."""
    operator = make_client(alice)
    review_session, first, second = _setup_two_instrument_session(
        operator, db, code="rae-e-pos-pages"
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
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][comments]": "page-1 only",
            f"response[{page2_assignment.id}][comments]": "page-2 only",
            "current_position": "1",
        },
        follow_redirects=False,
    )
    body = response.text
    # Banner enumerates each gap, prefixed with `Page N:` per spec.
    assert "Required fields missing" in body
    assert "<strong>Page 1:</strong>" in body
    assert "<strong>Page 2:</strong>" in body


def test_submit_missing_only_on_page_two_still_carries_page_number(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Required gap only on Page 2 → banner names Page 2 explicitly so
    the reviewer doesn't waste time looking on the current page."""
    operator = make_client(alice)
    review_session, first, second = _setup_two_instrument_session(
        operator, db, code="rae-e-pos-2only"
    )
    # Fill in Page 1's required `rating` field; leave Page 2 blank.
    page1_assignment = db.execute(
        select(Assignment)
        .where(Assignment.session_id == review_session.id)
        .where(Assignment.instrument_id == first.id)
    ).scalar_one()

    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][rating]": "5",
            "current_position": "1",
        },
        follow_redirects=False,
    )
    body = response.text
    assert "Required fields missing" in body
    assert "<strong>Page 2:</strong>" in body


# ── Operator preview adapts to PR ε chrome ───────────────────────────────


def test_preview_action_row_collapses_to_page_buttons(
    client: TestClient, db: Session
) -> None:
    """Operator preview renders a unified action row that collapses to
    just Page #N buttons. Save / Discard / divider / Submit are
    suppressed because preview is read-only and synthetic."""
    client.post(
        "/operator/sessions",
        data={"name": "Prev", "code": "prev-eps-collapse"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "prev-eps-collapse")
    ).scalar_one()
    body = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    ).text
    # Page #1 button renders even on single-instrument preview.
    assert 'data-rs-page="1"' in body
    # No Save / Discard / Submit / divider in preview. ``data-rs-save>``
    # is a whole-token check that doesn't collide with
    # ``data-rs-saved-value`` on the synthetic inputs.
    assert "data-rs-save>" not in body
    assert "data-rs-discard>" not in body
    assert 'class="rs-action-divider"' not in body
    assert (
        f'formaction="/reviewer/sessions/{review_session.id}/submit"'
        not in body
    )


def test_preview_status_panel_renders_without_per_page_pills(
    client: TestClient, db: Session
) -> None:
    """Per the spec, the preview status panel renders without per-page
    pills (preview is read-only and synthetic; per-page state is
    moot). The panel itself stays in the layout so the side-by-side
    grid keeps shape."""
    client.post(
        "/operator/sessions",
        data={"name": "Prev", "code": "prev-eps-pills"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "prev-eps-pills")
    ).scalar_one()
    body = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    ).text
    # Status panel is part of the bottom-grid layout shared with the
    # live surface. Per-page pills (`rs-page-status-pills`) are
    # suppressed in preview.
    assert 'class="rs-page-status-pills"' not in body


def test_preview_inputs_render_disabled(
    client: TestClient, db: Session
) -> None:
    """Preview's read-only contract — every input renders ``disabled``
    so the operator can't type into a synthetic surface."""
    client.post(
        "/operator/sessions",
        data={"name": "Prev", "code": "prev-eps-disabled"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "prev-eps-disabled")
    ).scalar_one()
    body = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    ).text
    # Every actual response input on the synthetic surface carries
    # ``disabled``. Anchor on the seeded `rating` field.
    assert 'name="response' in body
    # At least one input/textarea/select with `disabled` lands; verify
    # via the `name="response"` token co-occurring with `disabled`.
    response_input_idx = body.find('name="response')
    assert response_input_idx >= 0
    # Look forward up to 200 chars for the `disabled` attribute on the
    # same tag.
    assert "disabled" in body[response_input_idx : response_input_idx + 300]


def test_preview_omits_pushstate_prefix(
    client: TestClient, db: Session
) -> None:
    """The ``data-rs-pushstate-prefix`` attribute on `.rs-paginated`
    is omitted in preview so Page #N click toggles visibility without
    rewriting the URL bar (which would push reviewer-side URLs into
    the operator's history)."""
    client.post(
        "/operator/sessions",
        data={"name": "Prev", "code": "prev-eps-nopush"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "prev-eps-nopush")
    ).scalar_one()
    body = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    ).text
    # The attribute itself (``data-rs-pushstate-prefix="..."``) is
    # absent; the substring still appears inside JS comments, so
    # match the attribute-with-equals form.
    assert "data-rs-pushstate-prefix=" not in body
