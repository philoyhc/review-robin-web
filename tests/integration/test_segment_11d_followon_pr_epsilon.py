"""PR ε — Acknowledge missing required (session-wide) + preview adaptation.

Per `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on: Reviewer
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
        f"/me/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][comments]": "page-1 only",
            f"response[{page2_assignment.id}][comments]": "page-2 only",
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
        f"/me/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][rating]": "5",
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
    (`.rs-missing-card`) below the overview card — not inside it —
    because the list can be long enough that cramming it into the
    card produced a tall, narrow scroll."""
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
        f"/me/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][rating]": "5",
        },
        follow_redirects=False,
    ).text
    assert 'class="card rs-missing-card"' in body
    # Card sits *below* the overview card, as its own full-width
    # card — not inside it.
    panel_open = body.find('class="card rs-status-panel"')
    card_open = body.find('class="card rs-missing-card"')
    assert panel_open >= 0 and card_open >= 0
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
        f"/me/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][rating]": "5",
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
        f"/me/sessions/{review_session.id}/submit",
        data={
            f"response[{page1_assignment.id}][rating]": "5",
        },
        follow_redirects=False,
    ).text
    assert "data-rs-missing-dismiss" in body
    assert (
        f'href="/me/sessions/{review_session.id}/1">\n          Cancel\n        </a>'
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
        f"/me/sessions/{review_session.id}/1"
    ).text
    # The CSS rule for `.rs-missing-card` is always in the inline
    # stylesheet; assert on the element class + dismiss data attr's
    # closing `>` (the bare attr name appears inside CSS comments
    # that document the JS hook).
    assert 'class="card rs-missing-card"' not in body
    assert "data-rs-missing-dismiss>" not in body


# ── Operator preview adapts to PR ε chrome ───────────────────────────────


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


# ``test_preview_inputs_render_disabled`` retired in the Segment 18Q
# follow-on. The old iframe preview path forced ``accepting=False`` on
# every row so all inputs rendered ``disabled``; the new full-preview
# path bypasses session-lifecycle / acceptance gates and forces
# ``accepting=True`` so the operator sees the form exactly as a
# reviewer would when it's accepting responses. Write semantics are
# blocked at the action-row level (Save/Discard/Submit disabled) and
# the surrounding ``<form>`` is replaced by a ``<div>``, both covered
# by ``test_operator_preview_surface.py``.


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
