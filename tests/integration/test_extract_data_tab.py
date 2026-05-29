"""Skeleton for the new Extract data Operations-strip tab
(per ``guide/extract_data.md``). Verifies the route renders
200, surfaces the page heading, the three placeholder lens
sections, and that the tab appears in the operations strip on
its own page + on a sibling Operations page (Responses).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str = "extract-tab"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "ExtractTab", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_extract_data_tab_renders_skeleton(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-tab-basic")
    response = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    )
    assert response.status_code == 200, response.text
    body = response.text

    # Page heading.
    assert ">Extract all data</h2>" in body
    # Three lens placeholder sections present.
    assert 'id="extract-data-by-instrument"' in body
    assert 'id="extract-data-by-reviewer"' in body
    assert 'id="extract-data-by-reviewee"' in body
    # Lens headings — every lens card uses h2 to match the
    # Extract data intro card's text styling (Wave 2 PR — chip
    # row layout shipped).
    assert ">By instrument</h2>" in body
    assert ">By reviewer</h2>" in body
    assert ">By reviewee</h2>" in body


def test_extract_data_tab_appears_in_operations_strip(
    client: TestClient, db: Session
) -> None:
    """The Extract data tab is the last Operations tab (after
    Responses). Both the new page and the sibling Responses page
    should render the tab in their nav strip."""

    review_session = _make_session(client, db, code="ed-tab-nav")

    # On the new Extract data page itself, the tab is active.
    own = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    )
    assert own.status_code == 200
    assert "Extract data</a>" in own.text
    assert (
        f'href="/operator/sessions/{review_session.id}/extract-data"'
        in own.text
    )
    # The active class lands on the matching tab.
    assert 'class="nav-tab active"' in own.text

    # On a sibling Operations page (Responses), the tab also
    # appears (inactive).
    sibling = client.get(
        f"/operator/sessions/{review_session.id}/responses"
    )
    assert sibling.status_code == 200
    assert (
        f'href="/operator/sessions/{review_session.id}/extract-data"'
        in sibling.text
    )


def test_extract_data_tab_breadcrumbs(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-tab-crumbs")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # operator_session_child renders "Sessions › <name> › Extract data".
    assert "Extract data" in body


def test_extract_all_card_renders_lens_selector_chips(
    client: TestClient, db: Session
) -> None:
    """The intro card (now ``Extract all data``) carries three
    placeholder selector chips — ``By instruments``,
    ``By reviewers``, ``By reviewees`` — all defaulting to
    selected. Wiring lands later; this slice is layout."""
    review_session = _make_session(client, db, code="ed-all-chips")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    assert 'data-extract-all-chip="by-instruments"' in body
    assert ">By instruments<" in body
    assert 'data-extract-all-chip="by-reviewers"' in body
    assert ">By reviewers<" in body
    assert 'data-extract-all-chip="by-reviewees"' in body
    assert ">By reviewees<" in body

    # All three chips start selected.
    chip_block = body.split('id="extract-data-intro"')[1].split(
        "extract-data-card-actions"
    )[0]
    assert chip_block.count("is-selected") == 3
    assert chip_block.count('aria-pressed="true"') == 3


def test_by_instrument_card_renders_selectable_chips(
    client: TestClient, db: Session
) -> None:
    """The By instrument card carries one chip per instrument
    (by short label or ``Instrument_{n}`` fallback) plus the two
    cross-cutting toggles. All default to selected
    (``is-selected`` + ``aria-pressed="true"``)."""
    review_session = _make_session(client, db, code="ed-chips")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # Default-seeded session has one instrument with no short
    # label — the chip carries the bare ``#1`` positional prefix
    # (matches the Reviewer-surface heading helper's no-label
    # branch).
    assert "data-by-instrument-chip=\"instrument-" in body
    assert ">#1<" in body
    # Cross-cutting toggles.
    assert "data-by-instrument-chip=\"include-metadata\"" in body
    assert ">Include metadata<" in body
    assert "data-by-instrument-chip=\"all-assignment-rows\"" in body
    assert ">All assignment rows<" in body
    # All chips start selected — the toggle JS flips this later.
    chip_block = body.split("extract-data-by-instrument")[1].split(
        "extract-data-card-actions"
    )[0]
    assert chip_block.count("is-selected") >= 3
    assert chip_block.count('aria-pressed="true"') >= 3
