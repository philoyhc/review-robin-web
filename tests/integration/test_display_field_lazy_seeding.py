"""Integration tests for display-field lazy seeding —
reviewee CSV imports + manual-assignments imports backfill the
per-instrument display-field rows for any populated source slot,
and the GET /instruments page prunes rows whose underlying data
source is no longer populated.

Carved out of test_display_field_routes.py per
guide/major_refactor.md §12.D.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    InstrumentDisplayField,
    Reviewee,
)
from ._display_field_helpers import (
    _instrument,
    _make_session,
    _populate_rosters,
)

def test_reviewees_import_lazy_seeds_display_fields(
    client: TestClient, db: Session
) -> None:
    """After uploading reviewees with populated tag/profile columns, the
    Default instrument should gain corresponding display-field rows
    automatically — no operator action required (item #14). Locked
    Name + Email rows are seeded by ``ensure_default_instrument`` even
    before the reviewees import (Slice 1 of Segment 10D)."""
    review_session = _make_session(client, db, code="seed-on-import")
    instrument = _instrument(db, review_session.id)
    pre_rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    assert [(r.source_type, r.source_field) for r in pre_rows] == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
    ]

    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    b"RevieweeName,RevieweeEmail,RevieweeTag1,PhotoLink\n"
                    b"Carol,carol@example.edu,Cohort A,https://example.edu/c\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in rows]
    # Locked Name + Email rows + lazy-seeded profile_link + tag_1.
    assert pairs == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
        ("reviewee", "profile_link"),
        ("reviewee", "tag_1"),
    ]


def test_relationships_import_lazy_seeds_pair_context_display_fields(
    client: TestClient, db: Session
) -> None:
    """15D PR 6b: lazy-seeding fires from the relationships save now
    (post-Assignment.context drop). Uploading a Relationships CSV
    with populated tag slots should add the corresponding
    ``pair_context`` display fields to every instrument."""

    review_session = _make_session(client, db, code="seed-rel-import")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)

    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,PairContextTag1,PairContextTag2\n"
                    b"r@example.edu,carol@example.edu,morning,roomA\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in rows]
    assert ("pair_context", "1") in pairs
    assert ("pair_context", "2") in pairs
    assert ("pair_context", "3") not in pairs

def test_instruments_get_backfills_lazy_seeded_display_fields(
    client: TestClient, db: Session
) -> None:
    """Sessions whose reviewees / assignments were imported before the
    lazy-seeding logic landed end up missing the corresponding Display
    Fields rows. Hitting GET /instruments idempotently backfills them
    so the operator doesn't have to re-import to recover."""
    review_session = _make_session(client, db, code="backfill-on-get")
    instrument = _instrument(db, review_session.id)

    # Insert a reviewee with tag_1 + profile_link directly (skipping
    # the import path that would auto-seed).
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
            tag_1="Cohort A",
            profile_link="https://example.edu/c",
        )
    )
    db.commit()

    # Pre-condition: only the locked Name + Email rows from
    # ensure_default_instrument exist. No tag_1 / profile_link rows.
    pre = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    assert [(r.source_type, r.source_field) for r in pre] == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
    ]

    client.get(f"/operator/sessions/{review_session.id}/instruments")

    post = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in post]
    assert ("reviewee", "tag_1") in pairs
    assert ("reviewee", "profile_link") in pairs


def test_instruments_get_prunes_unpopulated_display_fields(
    client: TestClient, db: Session
) -> None:
    """If a Display Fields row's underlying data source has no data
    in the session (e.g. pair_context_1 was seeded by a prior import
    that's since been replaced), the row disappears on next GET.
    Locked Name + Email are kept regardless."""
    review_session = _make_session(client, db, code="prune-stale")
    instrument = _instrument(db, review_session.id)
    # Manually insert pair_context.1/2 + reviewee.tag_1 rows simulating
    # state from a prior import.
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="P1",
            source_type="pair_context",
            source_field="1",
            order=2,
            visible=True,
        )
    )
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="P2",
            source_type="pair_context",
            source_field="2",
            order=3,
            visible=True,
        )
    )
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="Cohort",
            source_type="reviewee",
            source_field="tag_1",
            order=4,
            visible=True,
        )
    )
    # Reviewee with tag_1 populated; no assignments → no pair_context.
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
            tag_1="Cohort A",
        )
    )
    db.commit()

    client.get(f"/operator/sessions/{review_session.id}/instruments")

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in rows]
    # pair_context.1/2 dropped (no data); locked rows + tag_1 kept.
    assert pairs == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
        ("reviewee", "tag_1"),
    ]
    # Operator-typed label on tag_1 ("Cohort") survives the prune.
    tag_1 = next(r for r in rows if r.source_field == "tag_1")
    assert tag_1.label == "Cohort"

