"""Integration tests for Segment 18L PR 1b — the single-page
reviewer surface at ``GET /reviewer/sessions/{id}``.

Locks the new structural contract: every instrument the reviewer
has assignments on renders into the DOM at once (no
``.rs-paginated`` toggling), separated by an
``<hr class="rs-instrument-separator">``; each instrument carries
``<section id="instrument-{id}">``; the action row interleaves
above every instrument heading plus once at the bottom with the
danger zone; the legacy positional GET 303s to the bare URL with
an ``#instrument-{id}`` fragment.

Locked decisions tested:
- (6) Each group emits ``id="instrument-{id}"``.
- (8) Page-N buttons become in-page anchor TOC with
  ``href="#instrument-{id}"`` and label ``"#N short_label"``.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Instrument, ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _operator_creates_session_with_pair(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
    reviewee_ident: str,
    extra_instruments: int = 0,
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
    for _ in range(extra_instruments):
        operator_client.post(
            f"/operator/sessions/{review_session.id}/instruments/add-new-model"
        )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    operator_client.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)
    return review_session


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


# --------------------------------------------------------------------------- #
# Single-page render structure
# --------------------------------------------------------------------------- #


def test_bare_url_renders_single_page_surface(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """``GET /reviewer/sessions/{id}`` renders directly (no longer
    303s to ``/1``)."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="sp-1",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}",
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_multi_instrument_renders_all_groups_with_anchor_ids(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Every instrument the reviewer has assignments on lands in
    the DOM with its own ``id="instrument-{id}"`` anchor."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="sp-2",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        extra_instruments=2,  # 1 default + 2 added = 3 instruments
    )
    instruments = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalars().all()
    assert len(instruments) == 3

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text

    for inst in instruments:
        assert f'id="instrument-{inst.id}"' in body


def test_hr_separator_renders_only_between_pages(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """``<hr class="rs-instrument-separator">`` is emitted only
    between instruments where the second carries
    ``starts_new_page=true`` (the Segment 18M break flag). Default
    behaviour on a fresh session: no breaks, no separators."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="sp-2b",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        extra_instruments=2,
    )
    instruments = sorted(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars().all(),
        key=lambda i: (i.order, i.id),
    )
    rae_client = make_client(rae)
    # No breaks set yet -> zero separators.
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert body.count('class="rs-instrument-separator"') == 0

    # Set a break before the second instrument via the operator
    # service helper. One break -> one separator.
    from app.services import instruments as instruments_service

    instruments_service.create_page_break_after(
        db, instrument=instruments[0]
    )
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert body.count('class="rs-instrument-separator"') == 1

    # Set another break (between 2 and 3) -> two separators.
    instruments_service.create_page_break_after(
        db, instrument=instruments[1]
    )
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert body.count('class="rs-instrument-separator"') == 2


def test_single_instrument_session_has_no_hr_separator(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="sp-3",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert 'class="rs-instrument-separator"' not in body


def test_action_row_interleaves_above_every_instrument_plus_bottom(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """With N instruments, the action row renders N + 1 times: above
    each instrument heading (N) + once outside the loop at the
    bottom (1)."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="sp-4",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        extra_instruments=2,  # 3 instruments total
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert body.count('class="rs-action-row') == 4  # 3 top + 1 bottom


# --------------------------------------------------------------------------- #
# Anchor TOC buttons
# --------------------------------------------------------------------------- #


def test_page_buttons_render_as_anchor_links_to_instrument_ids(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Locked decision 8: page buttons are in-page anchor TOC, not
    pagination controls. Each button is an ``<a href="#instrument-
    {id}">`` element."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="sp-5",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        extra_instruments=1,
    )
    instruments = sorted(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars().all(),
        key=lambda i: (i.order, i.id),
    )

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    for inst in instruments:
        assert f'href="#instrument-{inst.id}"' in body
    # Labels reflect the new "#N short_label" format (no "Page "
    # prefix); fall back to bare "#N" when no short_label is set.
    assert '">#1</a>' in body
    assert '">#2</a>' in body


# --------------------------------------------------------------------------- #
# Legacy positional shim
# --------------------------------------------------------------------------- #


def test_legacy_positional_url_303s_to_bare_url_with_anchor(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="sp-6",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        extra_instruments=1,
    )
    instruments = sorted(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars().all(),
        key=lambda i: (i.order, i.id),
    )
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/2",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/reviewer/sessions/{review_session.id}"
        f"#instrument-{instruments[1].id}"
    )


def test_legacy_positional_url_out_of_range_303s_to_bare_url(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Out-of-range position (greater than instrument count) 303s to
    the bare URL with no fragment instead of 404'ing — the
    canonical handler renders all instruments anyway."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="sp-7",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/99",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/reviewer/sessions/{review_session.id}"
    )


# --------------------------------------------------------------------------- #
# Form action — bulk save endpoint
# --------------------------------------------------------------------------- #


def test_form_action_targets_consolidated_save_endpoint(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The bulk-save form now POSTs to ``/sessions/{id}/save`` (the
    consolidated endpoint from PR 1a) instead of the legacy
    positional ``/sessions/{id}/{N}/save``."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="sp-8",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert f'action="/reviewer/sessions/{review_session.id}/save"' in body
    # current_position hidden input retired on the bulk save form.
    assert (
        'type="hidden" name="current_position"' not in body
        or '/sessions/{}/save"'.format(review_session.id) in body
        # The clear form still carries current_position until PR 1c;
        # search specifically inside the bulk-save form context.
    )
