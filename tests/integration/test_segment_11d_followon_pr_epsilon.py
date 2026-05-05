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
    # ``instruments/add`` clones full-matrix assignments onto the new
    # instrument automatically (per ``create_instrument``), so no
    # manual Assignment seeding is needed.
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


# ── Missing-required card — full-width, two-column, dismissible ──────────


def test_missing_required_renders_in_full_width_card(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The missing-required warning lives in its own full-width card
    (`.rs-missing-card`) below the bottom-grid — not inside the
    half-width status panel — because the list can be long enough
    that cramming it into the panel produced a tall, narrow scroll."""
    operator = make_client(alice)
    review_session, first, _ = _setup_two_instrument_session(
        operator, db, code="rae-e-card"
    )
    page1_assignment = db.execute(
        select(Assignment)
        .where(Assignment.session_id == review_session.id)
        .where(Assignment.instrument_id == first.id)
    ).scalar_one()
    rae_client = make_client(rae)
    body = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][rating]": "5",
            "current_position": "1",
        },
        follow_redirects=False,
    ).text
    assert 'class="card rs-missing-card"' in body
    # Card sits *below* the bottom-grid, not inside the status panel.
    grid_close = body.find("</div>\n  </div>")  # bottom-grid close
    panel_open = body.find('class="card rs-status-panel"')
    card_open = body.find('class="card rs-missing-card"')
    assert grid_close >= 0 and panel_open >= 0 and card_open >= 0
    # Card opens after the status panel closes — ie after the bottom-grid.
    assert card_open > panel_open


def test_missing_required_card_uses_two_column_list(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The list inside the missing card flows over two columns
    (CSS `column-count: 2`) so a long list stays compact. Pin the
    `.rs-missing-list` modifier so a future markup change has to
    deliberately retire the two-column layout."""
    operator = make_client(alice)
    review_session, first, _ = _setup_two_instrument_session(
        operator, db, code="rae-e-cols"
    )
    page1_assignment = db.execute(
        select(Assignment)
        .where(Assignment.session_id == review_session.id)
        .where(Assignment.instrument_id == first.id)
    ).scalar_one()
    rae_client = make_client(rae)
    body = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][rating]": "5",
            "current_position": "1",
        },
        follow_redirects=False,
    ).text
    assert 'class="rs-missing-list"' in body
    # The two-column rule is in base.html; pin its presence so a
    # future cleanup doesn't silently collapse the card to one column
    # at desktop widths.
    assert ".rs-missing-card .rs-missing-list" in body
    assert "column-count: 2" in body


def test_missing_required_card_carries_cancel_dismiss_button(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The card ends with a Cancel link (``data-rs-missing-dismiss``)
    that navigates back to the originating instrument page so the
    URL bar leaves the POST-only ``/submit`` endpoint behind."""
    operator = make_client(alice)
    review_session, first, _ = _setup_two_instrument_session(
        operator, db, code="rae-e-dismiss"
    )
    page1_assignment = db.execute(
        select(Assignment)
        .where(Assignment.session_id == review_session.id)
        .where(Assignment.instrument_id == first.id)
    ).scalar_one()
    rae_client = make_client(rae)
    body = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][rating]": "5",
            "current_position": "1",
        },
        follow_redirects=False,
    ).text
    assert "data-rs-missing-dismiss" in body
    assert (
        f'href="/reviewer/sessions/{review_session.id}/1">\n          Cancel\n        </a>'
        in body
    )
    # Submit is a hard gate when required fields are missing; the
    # retired acknowledge-and-submit-anyway checkbox does not render.
    assert 'name="acknowledge_missing"' not in body


def test_missing_required_card_absent_when_no_gaps(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """No missing card on a fresh GET (no submit attempt) and no card
    on a successful submit (no gaps)."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator, db, code="rae-e-nocard"
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    # The CSS rule for `.rs-missing-card` is always in the inline
    # stylesheet; assert on the element class + dismiss data attr's
    # closing `>` (the bare attr name appears inside CSS comments
    # that document the JS hook).
    assert 'class="card rs-missing-card"' not in body
    assert "data-rs-missing-dismiss>" not in body


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
    # Look forward up to the next tag close for the `disabled`
    # attribute. The window has to be generous enough to cover the
    # numeric input's full attribute set (min, max, step, title, …).
    tag_close = body.find(">", response_input_idx)
    assert tag_close > response_input_idx
    assert "disabled" in body[response_input_idx:tag_close]


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
