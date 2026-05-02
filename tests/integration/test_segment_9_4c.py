"""Tests for Segment 9.4C — Manage-page reshapes + instruments index +
``/setupinvite`` stub.

Covers:
- Reviewers / Reviewees / Assignments Manage pages render the anchored
  ``#upload-csv`` card and disabled Edit button.
- Assignments page renders the anchored ``#rules`` placeholder card.
- Removed ``…/import`` GET routes 404.
- ``/instruments`` index page renders one card per instrument, with
  Add / Delete instrument disabled.
- ``/setupinvite`` stub renders.
- ``build_setup_rows`` re-enables Instruments and Email Invites rows.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession
from app.web import views


def _make_session(
    client: TestClient, db: Session, *, code: str = "9-4c"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    return review_session


# ---------------------------------------------------------------------------
# Slice 1 — reviewers / reviewees Manage page reshape
# ---------------------------------------------------------------------------


def test_reviewers_page_renders_anchored_upload_card_and_disabled_edit(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="r-reshape")

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text

    # Always-rendered Upload card
    assert 'id="upload-csv"' in body
    assert (
        f'action="/operator/sessions/{review_session.id}/reviewers/import"'
        in body
    )
    # Edit Reviewers button rendered disabled (anchor, not button)
    assert "Edit Reviewers" in body
    assert 'aria-disabled="true"' in body
    assert 'title="Inline editing — coming soon"' in body


def test_reviewees_page_renders_anchored_upload_card_and_disabled_edit(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="e-reshape")

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text

    assert 'id="upload-csv"' in body
    assert (
        f'action="/operator/sessions/{review_session.id}/reviewees/import"'
        in body
    )
    assert "Edit Reviewees" in body
    assert 'aria-disabled="true"' in body


def test_reviewers_import_get_route_removed(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="r-no-get")

    response = client.get(
        f"/operator/sessions/{review_session.id}/reviewers/import"
    )

    assert response.status_code == 405 or response.status_code == 404


def test_reviewees_import_get_route_removed(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="e-no-get")

    response = client.get(
        f"/operator/sessions/{review_session.id}/reviewees/import"
    )

    assert response.status_code == 405 or response.status_code == 404


def test_reviewers_import_validation_errors_render_on_manage_page(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="r-bad")

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("bad.csv", b"ReviewerName\nAlice\n", "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 400
    body = response.text
    # Manage-page chrome: anchored upload card still present
    assert 'id="upload-csv"' in body
    # Validation issues partial rendered
    assert "Missing required column" in body


# ---------------------------------------------------------------------------
# Slice 2 — assignments Manage page reshape
# ---------------------------------------------------------------------------


def test_assignments_hub_inlines_method_forms(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(client, db, code="a-reshape")

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text

    # Both Upload Manual and Full Matrix forms now live inline on the hub.
    assert 'id="upload-csv"' in body
    assert (
        f'action="/operator/sessions/{review_session.id}/assignments/manual/import"'
        in body
    )
    assert (
        f'action="/operator/sessions/{review_session.id}/assignments/full-matrix"'
        in body
    )
    # Rule Based card is a placeholder
    assert "Rule Based Assignment" in body
    assert "Under Construction" in body


# ---------------------------------------------------------------------------
# Slice 3 — instruments index + setup-row re-enable
# ---------------------------------------------------------------------------


def test_instruments_index_renders_one_card_per_instrument(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="i-index")

    response = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )

    assert response.status_code == 200
    body = response.text
    instruments = list(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars()
    )
    assert len(instruments) == 1
    instrument = instruments[0]

    assert "<h1>Instruments</h1>" in body
    # Per-instrument card now uses 'Instrument #N' as its title; the
    # system handle is no longer surfaced in the card.
    assert ">Instrument #1</h2>" in body
    # accepting_responses pill matches backing data
    if instrument.accepting_responses:
        assert "accepting responses" in body
    else:
        assert "not accepting" in body


def test_build_setup_rows_re_enables_instruments_and_setup_invites(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rows-94c")

    rows = views.build_setup_rows(db, review_session)
    by_label = {r.label: r for r in rows}

    assert by_label["Instruments"].manage_disabled is False
    assert by_label["Instruments"].manage_url.endswith("/instruments")
    assert by_label["Email Invites"].manage_disabled is False
    assert by_label["Email Invites"].manage_url.endswith("/setupinvite")


# ---------------------------------------------------------------------------
# Slice 4 — /setupinvite stub
# ---------------------------------------------------------------------------


def test_setupinvite_stub_renders(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="setupinvite")

    response = client.get(
        f"/operator/sessions/{review_session.id}/setupinvite"
    )

    assert response.status_code == 200
    body = response.text
    assert "<h1>Email Template</h1>" in body
    assert "Segment 15" in body


# ---------------------------------------------------------------------------
# Session detail Manage buttons reach the new pages
# ---------------------------------------------------------------------------


def test_session_detail_links_instruments_and_setupinvite(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="hub-links")

    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Manage buttons for Instruments and Email Invites are real anchors
    assert (
        f'href="/operator/sessions/{review_session.id}/instruments"' in body
    )
    assert (
        f'href="/operator/sessions/{review_session.id}/setupinvite"' in body
    )
