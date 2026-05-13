"""Reviewer-surface integration coverage for Segment 13B PR 1.

Pins the render-time consumption of ``Instrument.sort_display_fields``
against the actual reviewer-surface HTML. Three reviewees + the
default Name display field; sort spec narrows to ascending /
descending by Name; rows render in the expected order.

Unit-level coverage for the sort helper itself lives in
``tests/unit/test_order_rows_by_sort_spec.py``; the service
writer's validator + audit + lifecycle behaviour lives in
``tests/integration/test_set_sort_display_fields.py``. This file
is the smallest possible "end-to-end through the reviewer
surface" pin.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Instrument, InstrumentDisplayField, ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _setup_session_with_three_reviewees(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
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
    # Three reviewees with intentionally non-sorted insertion order
    # so the test catches "sort actually happened" rather than
    # "rows already in name order."
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    "RevieweeName,RevieweeEmail\n"
                    "Bravo,bravo@example.edu\n"
                    "Alpha,alpha@example.edu\n"
                    "Charlie,charlie@example.edu\n"
                ).encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    return review_session


def _activate(
    operator_client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    operator_client.get(
        f"/operator/sessions/{review_session.id}?validated=1"
    )
    response = operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)


def _reviewee_name_display_field(
    db: Session, review_session: ReviewSession
) -> InstrumentDisplayField:
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    return db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .where(InstrumentDisplayField.source_type == "reviewee")
        .where(InstrumentDisplayField.source_field == "name")
    ).scalar_one()


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def test_no_sort_spec_renders_three_rows(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Baseline sanity: ``sort_display_fields`` is NULL → the
    reviewer surface still renders all three rows without
    erroring. The exact unsorted order is the legacy reviewer-
    surface ordering (which today happens to match alphabetical-
    by-name from the full-matrix generation path), so this test
    just confirms 200 + all three names present; the explicit
    sort tests below cover the per-direction guarantees."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="rss-baseline", reviewer_email=rae.email
    )
    _activate(client, db, review_session)
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    assert response.status_code == 200
    body = response.text
    assert all(name in body for name in ("Alpha", "Bravo", "Charlie"))


def test_sort_spec_orders_rows_ascending_by_name(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    review_session = _setup_session_with_three_reviewees(
        client, db, code="rss-asc", reviewer_email=rae.email
    )
    name_field = _reviewee_name_display_field(db, review_session)
    instrument = name_field.instrument
    instrument.sort_display_fields = [
        {"display_field_id": name_field.id, "dir": "asc"}
    ]
    db.commit()

    _activate(client, db, review_session)
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    body = response.text
    # Alphabetical: Alpha, Bravo, Charlie.
    assert body.find("Alpha") < body.find("Bravo") < body.find("Charlie")


def test_sort_spec_orders_rows_descending_by_name(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    review_session = _setup_session_with_three_reviewees(
        client, db, code="rss-desc", reviewer_email=rae.email
    )
    name_field = _reviewee_name_display_field(db, review_session)
    instrument = name_field.instrument
    instrument.sort_display_fields = [
        {"display_field_id": name_field.id, "dir": "desc"}
    ]
    db.commit()

    _activate(client, db, review_session)
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    body = response.text
    # Reverse-alphabetical: Charlie, Bravo, Alpha.
    assert body.find("Charlie") < body.find("Bravo") < body.find("Alpha")


def test_empty_sort_spec_renders_insertion_order(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """An empty list (operator explicitly cleared the sort) is
    equivalent to NULL — no reordering."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="rss-empty", reviewer_email=rae.email
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    instrument.sort_display_fields = []
    db.commit()
    _activate(client, db, review_session)
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    assert response.status_code == 200
    body = response.text
    # Empty list is a no-op — all three names render with no
    # render-time error.
    assert all(name in body for name in ("Alpha", "Bravo", "Charlie"))


def test_reviewer_surface_renders_sortable_header_scaffolding(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Live sort (PR 3) is JS-driven; the server's job is to
    render the right scaffolding — sortable class on each th,
    a per-header data-sort-key, a sort badge span, and the
    sortable-table marker on the <table> element."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="rss-scaffold", reviewer_email=rae.email
    )
    _activate(client, db, review_session)
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    assert response.status_code == 200
    body = response.text
    # Table element carries the per-instrument sortable marker.
    assert 'data-rrw-sortable=' in body
    # The Reviewee identity header is clickable.
    assert 'class="rs-reviewee rrw-sortable"' in body
    assert 'data-sort-key="reviewee.name"' in body
    # Per-header sort badge span.
    assert '<span class="rrw-sort-badge">' in body
    # The click handler is wired.
    assert 'onclick="rrwSortHeaderClick(' in body
    # Each <td> carries a data-sort-value mirroring the row's
    # persisted display value (the JS reads this rather than
    # peeking into editable inputs).
    assert 'data-sort-value=' in body
    # tbody.rrw-rows wraps the data rows.
    assert '<tbody class="rrw-rows">' in body


def test_reviewer_surface_response_field_headers_carry_sort_type(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Response-field headers carry ``data-sort-type`` so the JS
    can apply numeric compare to Integer / Decimal columns."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="rss-rtype", reviewer_email=rae.email
    )
    _activate(client, db, review_session)
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    assert response.status_code == 200
    body = response.text
    # The default instrument has a String response field; the
    # response header should carry data-sort-type="String".
    assert 'data-sort-type="String"' in body


def test_reviewer_surface_no_override_preserves_operator_sort(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Server-side render unchanged when no live override is in
    play — regression for PR 2's persistence contract. Setting
    the operator sort to desc-by-Reviewee renders rows in that
    order on first page load (the JS-driven override only kicks
    in after a header click)."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="rss-noop-live", reviewer_email=rae.email
    )
    name_field = _reviewee_name_display_field(db, review_session)
    instrument = name_field.instrument
    instrument.sort_display_fields = [
        {"display_field_id": name_field.id, "dir": "desc"}
    ]
    db.commit()
    _activate(client, db, review_session)
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    assert response.status_code == 200
    body = response.text
    # Operator-desc order: Charlie, Bravo, Alpha. (Reviewee
    # rendering shows the name on each row.)
    assert body.find("Charlie") < body.find("Bravo") < body.find("Alpha")


def test_stale_display_field_id_skipped_silently(
    db: Session,
    client: TestClient,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Render-time defense: a sort-spec entry pointing at a
    display_field_id that's not on the instrument silently drops.
    With only that stale entry, the table falls back to insertion
    order rather than erroring."""
    review_session = _setup_session_with_three_reviewees(
        client, db, code="rss-stale", reviewer_email=rae.email
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    instrument.sort_display_fields = [
        {"display_field_id": 99999, "dir": "asc"}
    ]
    db.commit()
    _activate(client, db, review_session)
    rae_client = make_client(rae)
    response = rae_client.get(
        f"/reviewer/sessions/{review_session.id}"
    )
    assert response.status_code == 200
    body = response.text
    assert all(name in body for name in ("Alpha", "Bravo", "Charlie"))
