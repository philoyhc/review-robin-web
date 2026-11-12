"""Segment 20M rung 5 — where display fields sit on the reviewer surface.

Through the operator's *Preview as reviewer* (the reviewer surface's own
template). An individual instrument shows a tag display field as a column
(``across``), a labeled line under the email (``stacked``) or one line of
values (``joined``); a group-scoped one puts the member names first and
the tags below, one plain line (``joined``, or a stored ``across``) or a
labeled line each (``stacked``), never bold.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentDisplayField, Reviewee, ReviewSession

from .test_operator_preview_surface import _make_session_with_reviewer


def _surface(
    client: TestClient, db: Session, code: str, *, layout: str, group: bool = False
) -> str:
    review_session: ReviewSession = _make_session_with_reviewer(client, db, code=code)
    for reviewee in db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars():
        reviewee.tag_1 = "TW01"
        reviewee.tag_2 = "Team 2"
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    for slot, order in (("tag_1", 5), ("tag_2", 6)):
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type="reviewee",
                source_field=slot,
                order=order,
                visible=True,
            )
        )
    instrument.display_layout = layout
    if group:
        instrument.group_kind = "r1"
    db.commit()
    response = client.get(f"/operator/sessions/{review_session.public_id}/preview-surface/1")
    assert response.status_code == 200, response.text
    return " ".join(response.text.split())


def _identity(flat: str) -> str:
    match = re.search(r'<td class="rs-(?:reviewee|group)"[^>]*>(.*?)</td>', flat)
    assert match is not None
    return match.group(1)


def test_across_keeps_a_column_per_field(client: TestClient, db: Session) -> None:
    flat = _surface(client, db, "20m-across", layout="across")
    assert 'data-sort-key="display:reviewee.tag_1"' in flat
    assert "rs-df-line" not in _identity(flat)


def test_stacked_puts_a_labeled_line_per_field_under_the_email(
    client: TestClient, db: Session
) -> None:
    flat = _surface(client, db, "20m-stacked", layout="stacked")
    assert 'data-sort-key="display:reviewee.tag_1"' not in flat
    cell = _identity(flat)
    assert re.search(
        r"</code> <div class=\"rs-df-line\"><span class=\"muted\">[^<]+:</span> TW01</div>"
        r"<div class=\"rs-df-line\"><span class=\"muted\">[^<]+:</span> Team 2</div>",
        cell,
    ), cell


def test_joined_puts_the_values_on_one_line(client: TestClient, db: Session) -> None:
    flat = _surface(client, db, "20m-joined", layout="joined")
    assert 'data-sort-key="display:reviewee.tag_1"' not in flat
    assert '</code> <div class="rs-df-line">TW01, Team 2</div>' in _identity(flat)


@pytest.mark.parametrize("layout", ["joined", "across"])
def test_a_group_joins_its_tags_below_the_names_unbolded(
    client: TestClient, db: Session, layout: str
) -> None:
    flat = _surface(client, db, f"20m-group-{layout}", layout=layout, group=True)
    cell = _identity(flat)
    assert "<strong>" not in cell
    names = cell.index('<span class="muted">')
    tags = cell.index('<div class="rs-df-line">TW01, Team 2</div>')
    assert names < tags


def test_a_stacked_group_labels_each_tag_below_the_names(client: TestClient, db: Session) -> None:
    flat = _surface(client, db, "20m-group-stacked", layout="stacked", group=True)
    cell = _identity(flat)
    assert "<strong>" not in cell
    names = cell.index('<span class="muted">')
    first = cell.index('<div class="rs-df-line"><span class="muted">')
    assert names < first
    assert re.search(r'<span class="muted">[^<]+:</span> TW01</div>', cell)
    assert re.search(r'<span class="muted">[^<]+:</span> Team 2</div>', cell)


def test_a_sort_on_a_field_that_heads_no_column_is_inert(client: TestClient, db: Session) -> None:
    """A stored sort entry on a Stacked field sorts nothing (the plan's
    Semantics), as Profile's doesn't; across, the same entry orders the
    rows."""
    for layout, expect_tag_order in (("across", True), ("stacked", False)):
        review_session = _make_session_with_reviewer(
            client,
            db,
            code=f"20m-sort-{layout}",
            reviewee_idents=["a@example.edu", "b@example.edu"],
        )
        reviewees = list(
            db.execute(
                select(Reviewee)
                .where(Reviewee.session_id == review_session.id)
                .order_by(Reviewee.id)
            ).scalars()
        )
        # Tag order is the reverse of insertion order.
        reviewees[0].tag_1, reviewees[1].tag_1 = "Z", "A"
        instrument = db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalar_one()
        tag = InstrumentDisplayField(
            instrument_id=instrument.id,
            label="",
            source_type="reviewee",
            source_field="tag_1",
            order=5,
            visible=True,
        )
        db.add(tag)
        db.flush()
        instrument.sort_display_fields = [{"display_field_id": tag.id, "dir": "asc"}]
        instrument.display_layout = layout
        db.commit()
        body = client.get(f"/operator/sessions/{review_session.public_id}/preview-surface/1").text
        first = body.index("b@example.edu") < body.index("a@example.edu")
        assert first is expect_tag_order, layout
