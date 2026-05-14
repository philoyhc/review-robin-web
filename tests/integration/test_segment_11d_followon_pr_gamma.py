"""PR γ — Reviewer surface multi-instrument rewrite.

Per `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on: Reviewer
surface — multi-instrument rewrite" → PR γ. Replaces the dual top +
bottom action rows with a single unified `.rs-action-row` per side
(Save / Discard / `Page #N: {short_label}` / divider / Submit),
swaps the `<h2>{group.heading}</h2>` block for a
`.rs-instrument-heading` title+subtitle row, narrows rendering to
the URL position's instrument group, and adds a per-position Save
filter as defense in depth against malformed POSTs.
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
    first_short_label: str | None = None,
    first_description: str | None = None,
    second_short_label: str | None = None,
    second_description: str | None = None,
) -> tuple[ReviewSession, Instrument, Instrument]:
    """Build a ready (Activated) session with two instruments and one
    Assignment per instrument for the same reviewer/reviewee pair.

    Used by tests that need to exercise multi-instrument page-button
    labels, heading composition, and the per-position Save filter.
    """
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
    # manual Assignment seeding is needed. Apply heading metadata via
    # the service helper (the operator route writes through it;
    # either path is fine for fixtures).
    if first_short_label is not None:
        instruments_service.update_short_label(
            db, instrument=first, short_label=first_short_label, actor=None
        )
    if first_description is not None:
        instruments_service.update_instrument_description(
            db, instrument=first, description=first_description, actor=None
        )
    if second_short_label is not None:
        instruments_service.update_short_label(
            db, instrument=second, short_label=second_short_label, actor=None
        )
    if second_description is not None:
        instruments_service.update_instrument_description(
            db,
            instrument=second,
            description=second_description,
            actor=None,
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


# ── Action row order ─────────────────────────────────────────────────────


def test_action_row_orders_save_discard_pages_divider_submit(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The unified `.rs-action-row` lays out left-to-right as
    Save / Discard / Page #1 / Page #2 / divider / Submit. Each side
    of the surface mirrors this order; here we just assert the first
    occurrence."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator, db, code="rae-g-order"
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text

    save_idx = body.find("data-rs-save")
    discard_idx = body.find("data-rs-discard")
    page1_idx = body.find('data-rs-page="1"')
    page2_idx = body.find('data-rs-page="2"')
    divider_idx = body.find('class="rs-action-divider"')
    submit_idx = body.find("/submit")

    assert -1 < save_idx < discard_idx < page1_idx < page2_idx < divider_idx < submit_idx


def test_action_row_renders_mirrored_top_and_bottom(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The action row is included twice — once above the tables and
    once below. The divider shows up at least twice as a result."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator, db, code="rae-g-mirror"
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text

    assert body.count('class="rs-action-divider"') == 2
    # Two rs-action-row instances: top (carries the `rs-action-row-top`
    # modifier so it can be left-aligned with extra space above) and
    # bottom (default class string).
    assert body.count('class="rs-action-row rs-action-row-top"') == 1
    assert body.count('class="rs-action-row"') == 1


# ── Page-button labels ───────────────────────────────────────────────────


def test_page_button_label_uses_short_label_when_set(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Operators who've set ``Instrument.short_label`` get the friendly
    ``Page #N: {short_label}`` button label."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator,
        db,
        code="rae-g-shortlbl",
        first_short_label="Self-eval",
        second_short_label="Peer review",
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    assert "Page #1: Self-eval" in body
    assert "Page #2: Peer review" in body


def test_page_button_label_falls_back_to_position_only(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When ``short_label`` isn't set, the page button degrades to a
    bare ``Page #N`` label with no trailing colon."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator, db, code="rae-g-noshort"
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    # No trailing colon when the short_label is absent.
    assert "Page #1:" not in body
    assert "Page #2:" not in body
    assert "Page #1" in body
    assert "Page #2" in body


# ── Per-instrument heading composition ───────────────────────────────────


def test_instrument_heading_multi_with_short_label_and_description(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Multi-instrument + short_label + description → title is
    ``Page #N: {short_label}``, subtitle is the description."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator,
        db,
        code="rae-g-h-multi-both",
        first_short_label="Self-eval",
        first_description="Reflect on your own progress.",
        second_short_label="Peer review",
        second_description="Rate your teammates.",
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    # PR γ wrapped the heading in a flex `.rs-instrument-heading` row
    # of bare text; the per-instrument intro grid follow-up moved it
    # into a half-width `.card.rs-instrument-card` so the heading +
    # first help text card sit side-by-side.
    assert 'class="card rs-instrument-card"' in body
    assert "<h2>Page #1: Self-eval</h2>" in body
    assert "Reflect on your own progress." in body
    assert 'class="rs-instrument-subtitle muted"' in body


def test_instrument_heading_multi_short_label_only(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Multi-instrument + short_label, no description → title is
    ``Page #N: {short_label}`` and no subtitle span renders."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator,
        db,
        code="rae-g-h-multi-short",
        first_short_label="Self-eval",
        second_short_label="Peer review",
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    assert "<h2>Page #1: Self-eval</h2>" in body
    assert 'class="rs-instrument-subtitle muted"' not in body


def test_instrument_heading_multi_description_only(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Multi-instrument + description, no short_label → title is bare
    ``Page #N`` and the description renders as the subtitle."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator,
        db,
        code="rae-g-h-multi-desc",
        first_description="Reflect on your own progress.",
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    assert "<h2>Page #1</h2>" in body
    assert "Reflect on your own progress." in body
    assert 'class="rs-instrument-subtitle muted"' in body


def test_instrument_heading_multi_neither(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Multi-instrument with neither short_label nor description → bare
    ``Page #N`` title, no subtitle."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator, db, code="rae-g-h-multi-none"
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    assert "<h2>Page #1</h2>" in body
    assert 'class="rs-instrument-subtitle muted"' not in body


def test_instrument_heading_single_short_label_only(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Single-instrument + short_label → title is the short_label
    verbatim (no ``Page #1:`` prefix). Single-instrument sessions
    don't need page-numbering."""
    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Solo", "code": "rae-g-h-solo-short"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rae-g-h-solo-short")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,rae@example.edu\n",
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
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Self-eval", actor=None
    )
    operator.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
    operator.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )

    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    assert "<h2>Self-eval</h2>" in body
    # No Page #1 prefix in the *heading* — single-instrument sessions
    # don't need page-numbering. The page-button anchor still renders
    # ``Page #1: Self-eval`` in the action row.
    assert "<h2>Page #1: Self-eval</h2>" not in body


# ── Per-position Save filter (defense in depth) ──────────────────────────


def test_save_drops_cross_page_assignment_inputs(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Save's per-position filter drops ``response[<aid>][...]`` inputs
    whose assignment belongs to a different instrument than the URL
    position. Defense-in-depth against malformed POSTs (the GET surface
    already narrows rendering to one page so the form normally only
    contains its own page's inputs)."""
    operator = make_client(alice)
    review_session, first, second = _setup_two_instrument_session(
        operator, db, code="rae-g-save-filter"
    )
    # Both assignments exist for the same reviewer/reviewee pair.
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
    # POST to /1/save with inputs for both pages — the page-2 entry
    # must be filtered out.
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={
            f"response[{page1_assignment.id}][comments]": "page-1 ok",
            f"response[{page2_assignment.id}][comments]": "page-2 leak",
            "current_position": "1",
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
    assert any(r.value == "page-1 ok" for r in page1_responses)
    # Cross-page leak silently dropped.
    assert not any(r.value == "page-2 leak" for r in page2_responses)


# ── Rendering narrows to current position ────────────────────────────────


def test_surface_renders_all_groups_marks_current_active(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """PR δ — every instrument group lives in the DOM at once
    (rendered into ``.rs-paginated``); only the URL position's group
    carries the ``rs-active`` modifier. CSS hides non-active groups
    so dirty edits in hidden groups survive client-side navigation."""
    operator = make_client(alice)
    review_session, _, _ = _setup_two_instrument_session(
        operator,
        db,
        code="rae-d-allgroups",
        first_short_label="Self-eval",
        second_short_label="Peer review",
    )
    rae_client = make_client(rae)
    body_p1 = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    # Both headings render — non-active group is hidden via CSS, not
    # omitted from the markup.
    assert "<h2>Page #1: Self-eval</h2>" in body_p1
    assert "<h2>Page #2: Peer review</h2>" in body_p1
    assert (
        '<div class="rs-instrument-group rs-active"' in body_p1
        and 'data-rs-position="1"' in body_p1
    )
    # Position 2 group is present without rs-active.
    assert (
        '<div class="rs-instrument-group"' in body_p1
        and 'data-rs-position="2"' in body_p1
    )

    body_p2 = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/2"
    ).text
    assert "<h2>Page #2: Peer review</h2>" in body_p2
    assert "<h2>Page #1: Self-eval</h2>" in body_p2
    # Active group flips to position 2 on /2.
    assert (
        '<div class="rs-instrument-group rs-active"' in body_p2
        and 'data-rs-position="2"' in body_p2
    )
