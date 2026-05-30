"""Integration tests for Segment 18L PR 1b (post-replan) — the
multi-page reviewer surface at ``GET /me/sessions/{id}/{N}``.

The reviewer surface paginates by operator-defined page (one
boundary per ``Instrument.starts_new_page=true`` from Segment
18M). Each page renders one or more instruments together. The
bare URL 303s to page 1; positional URLs render the matching
page; out-of-range page numbers 404.

Locked decisions tested:
- Bare URL redirects to page 1 (post-replan: matches pre-18L).
- ``POST /sessions/{id}/{N}/save`` saves the page's inputs and
  303s back to that page.
- Each instrument renders one ``<section data-rs-position="N">``
  block (used here as the structural anchor for set-membership
  assertions across pages).
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
# Bare URL → page 1 redirect
# --------------------------------------------------------------------------- #


def test_bare_url_303s_to_page_1(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="mp-1",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/me/sessions/{review_session.id}",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/me/sessions/{review_session.id}/1"
    )


# --------------------------------------------------------------------------- #
# Per-page render
# --------------------------------------------------------------------------- #


def test_page_one_renders_first_pages_instruments(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="mp-2",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        extra_instruments=2,  # 3 instruments, all on one page (no breaks)
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/me/sessions/{review_session.id}/1").text
    # All three instrument sections render on page 1 since no break exists.
    for n in (1, 2, 3):
        assert f'data-rs-position="{n}"' in body


def test_out_of_range_page_returns_404(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="mp-3",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/me/sessions/{review_session.id}/99",
        follow_redirects=False,
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Page-break carving
# --------------------------------------------------------------------------- #


def test_page_break_carves_session_into_separate_pages(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """An operator-set page break between instrument N and N+1 means
    instrument N+1 lands on page 2 (no longer rendered on page 1)."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="mp-4",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        extra_instruments=1,  # 2 instruments
    )
    instruments = sorted(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars().all(),
        key=lambda i: (i.order, i.id),
    )
    from app.services import instruments as instruments_service

    instruments_service.create_page_break_after(
        db, instrument=instruments[0]
    )
    rae_client = make_client(rae)

    # Page 1 has only the first instrument (position 1).
    page1 = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    assert 'data-rs-position="1"' in page1
    assert 'data-rs-position="2"' not in page1

    # Page 2 has only the second (position 2).
    page2 = rae_client.get(
        f"/me/sessions/{review_session.id}/2"
    ).text
    assert 'data-rs-position="1"' not in page2
    assert 'data-rs-position="2"' in page2

    # Page 3 doesn't exist.
    response = rae_client.get(
        f"/me/sessions/{review_session.id}/3",
        follow_redirects=False,
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Form action + save redirect
# --------------------------------------------------------------------------- #


def test_form_action_targets_per_page_save_endpoint(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="mp-5",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    assert (
        f'action="/me/sessions/{review_session.id}/1/save"' in body
    )


def test_save_303s_back_to_current_page(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="mp-6",
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
    from app.services import instruments as instruments_service

    instruments_service.create_page_break_after(
        db, instrument=instruments[0]
    )
    rae_client = make_client(rae)
    # Page 2 save 303s back to /2.
    response = rae_client.post(
        f"/me/sessions/{review_session.id}/2/save",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/me/sessions/{review_session.id}/2"
    )


# --------------------------------------------------------------------------- #
# Page nav
# --------------------------------------------------------------------------- #


def test_multi_page_renders_prev_next_nav(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="mp-7",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        extra_instruments=2,  # 3 instruments
    )
    instruments = sorted(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars().all(),
        key=lambda i: (i.order, i.id),
    )
    from app.services import instruments as instruments_service

    # Break between #1 and #2 + between #2 and #3 -> 3 pages.
    instruments_service.create_page_break_after(
        db, instrument=instruments[0]
    )
    instruments_service.create_page_break_after(
        db, instrument=instruments[1]
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/me/sessions/{review_session.id}/2"
    ).text
    # Page 2 of 3 -> Prev to page 1, Next to page 3.
    assert "Page 2 of 3" in body
    assert (
        f'href="/me/sessions/{review_session.id}/1"' in body
    )
    assert (
        f'href="/me/sessions/{review_session.id}/3"' in body
    )


def test_single_page_session_omits_page_nav(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When there's only one page (no breaks set), the page-nav row
    is suppressed entirely — no Prev/Next, no 'Page 1 of 1'
    counter."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="mp-8",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    assert "Page 1 of" not in body
    assert "Previous page" not in body
    assert "Next page" not in body
