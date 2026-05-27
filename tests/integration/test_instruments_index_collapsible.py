"""Smoke tests for Segment 18M PR 0 — collapsible instrument
cards on the operator Instruments page. Locks the structural
contract PRs 2 + 3 will build on (drag-and-drop handle, page
break cards) so a refactor doesn't silently regress the
collapse surface.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str = "18m-pr0"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_each_instrument_renders_as_collapsible_details(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="18m-1")
    # Default seed = one instrument.
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    instruments = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalars().all()
    assert len(instruments) == 1
    # One <details.instrument-card-collapsible> per instrument.
    assert body.count('details class="instrument-card-collapsible"') == 1
    # Default state: collapsed (no `open` attribute on a fresh card).
    assert (
        '<details class="instrument-card-collapsible" open'
        not in body
    )


def test_summary_holds_title_and_both_status_pills(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="18m-2")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # The <summary> carries the title (keyed off instrument.id) and
    # the per-instrument Set up / Not set up pill (matches the
    # workflow card's is_configured predicate). A fresh instrument
    # has no Band 1 touched links, so it renders "Not set up".
    assert '<summary class="instrument-card-summary">' in body
    assert "Instrument #1" in body
    assert ">Not set up</span>" in body


def test_summary_carries_drag_handle_and_chevron(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="18m-3")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Drag handle placeholder PR 2 will bind to.
    assert "data-instrument-drag-handle" in body
    assert 'class="instrument-card-drag-handle"' in body
    # Chevron toggle icon (rotates via CSS, no JS hook).
    assert 'class="instrument-card-toggle-icon"' in body


def test_bulk_expand_and_collapse_buttons_render(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="18m-4")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert ">Expand all instruments</button>" in body
    assert ">Collapse all instruments</button>" in body
    assert "data-instruments-expand-all" in body
    assert "data-instruments-collapse-all" in body
    # Both buttons must be enabled (no `disabled` attribute on
    # the PR-0-wired bulk controls). Match the open tag forms.
    assert "data-instruments-expand-all disabled" not in body
    assert "data-instruments-collapse-all disabled" not in body


def test_multiple_instruments_render_multiple_details(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="18m-5")
    # Add a second instrument so the loop renders twice.
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model"
    )
    instruments = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalars().all()
    assert len(instruments) == 2
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert body.count('details class="instrument-card-collapsible"') == 2
    assert body.count('<summary class="instrument-card-summary">') == 2
