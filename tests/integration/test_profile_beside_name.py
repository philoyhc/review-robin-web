"""Segment 20M Item 1 — Profile rides beside the reviewee's name.

On the reviewer surface Profile renders inline after the name (View for
a web link, ••• otherwise) and heads no column; a stored sort entry on it
is inert. In Band 3 its row sits right after Email, whatever its stored
order, with no ▲ ▼, but stays in the order the reorder save sends.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Instrument, InstrumentDisplayField, Reviewee, ReviewSession

from .test_reviewer_surface_display_fields import (
    _activate,
    _operator_creates_session_with_pair,
)

LINK = "https://example.edu/carol"


@pytest.fixture
def rae() -> AuthenticatedUser:
    """The reviewer ``_operator_creates_session_with_pair`` rosters."""
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _session(
    db: Session, operator: TestClient, code: str
) -> tuple[ReviewSession, Instrument, InstrumentDisplayField]:
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code=code,
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalar_one()
    reviewee.profile_link = LINK
    reviewee.tag_1 = "Blue"
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    # Tag 1 stored before Profile, so the pin has something to move past.
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="",
            source_type="reviewee",
            source_field="tag_1",
            order=5,
            visible=True,
        )
    )
    profile = InstrumentDisplayField(
        instrument_id=instrument.id,
        label="",
        source_type="reviewee",
        source_field="profile_link",
        order=10,
        visible=True,
    )
    db.add(profile)
    db.commit()
    return review_session, instrument, profile


def test_band3_pins_profile_after_email_with_no_arrows(
    db: Session, alice: AuthenticatedUser, make_client: Callable[[AuthenticatedUser], TestClient]
) -> None:
    operator = make_client(alice)
    review_session, instrument, _ = _session(db, operator, "20m-band3")
    flat = " ".join(
        operator.get(
            f"/operator/sessions/{review_session.public_id}/instruments?editing={instrument.id}"
        ).text.split()
    )
    rows = re.findall(r'<tr data-new-model-df-row data-key="([^"]+)"(.*?)</tr>', flat)
    keys = [key for key, _ in rows]
    assert keys[:3] == [
        "reviewee.name",
        "reviewee.email_or_identifier",
        "reviewee.profile_link",
    ], keys
    assert "reviewee.tag_1" in keys[3:]
    body = dict(rows)
    assert 'data-beside-name="true"' in body["reviewee.profile_link"]
    assert "data-new-model-df-move" not in body["reviewee.profile_link"]
    # Still in the order the reorder save sends.
    assert 'data-reorderable="true"' in body["reviewee.profile_link"]
    # The first movable row's ▲ is off: Profile above it doesn't move.
    up = re.search(r'data-new-model-df-move="up"[^>]*>', body[keys[3]])
    assert up is not None and "disabled" in up.group(0)


def test_the_surface_puts_profile_beside_the_name_and_sorts_nothing_by_it(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session, instrument, profile = _session(db, operator, "20m-surface")
    instrument.sort_display_fields = [{"display_field_id": profile.id, "dir": "asc"}]
    db.commit()
    _activate(operator, db, review_session)
    flat = " ".join(make_client(rae).get(f"/me/sessions/{review_session.public_id}").text.split())
    assert re.search(
        r'<strong>Carol</strong> <span class="rs-profile"> ?<a href="https://example.edu/carol"'
        r' aria-label="View — Carol">View</a>',
        flat,
    )
    assert ">Profile<" not in flat
    assert 'data-sort-key="display:reviewee.profile_link"' not in flat
    # Tag 1 keeps its column.
    assert 'data-sort-key="display:reviewee.tag_1"' in flat
