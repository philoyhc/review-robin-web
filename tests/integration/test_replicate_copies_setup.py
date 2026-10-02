"""A1 (2026-10-02): Replicate copies the instrument's set-up, not just
its fields.

The copy gets its own clone of the source's pinned rule set and copies
its short label, Band 1 touched links, Band 2 state and the
visible-when-closed flag; it does not take the page-break flag. Sort entries and column widths name fields by id, so they are
re-pointed at the copy's own fields (``spec/instruments.md``
"Replicate semantics")."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    SessionRuleSet,
    User,
)
from app.schemas.sessions import SessionCreate
from app.services import instruments, sessions

from ._full_matrix import pin_full_matrix_on_all_instruments


def _setup(db: Session) -> tuple[Session, Instrument, User]:
    op = User(email="op-replicate@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = sessions.create_session(
        db, user=op, payload=SessionCreate(name="Rep", code="rep-setup")
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    source = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalars().first()
    return review_session, source, op


def _ids(db: Session, model: type, instrument_id: int) -> list[int]:
    return list(
        db.execute(
            select(model.id)
            .where(model.instrument_id == instrument_id)
            .order_by(model.order, model.id)
        ).scalars()
    )


def test_replicate_clones_the_rule_and_copies_the_setup(db: Session) -> None:
    review_session, source, op = _setup(db)
    source.short_label = "Peer"
    source.band1_touched_links = ["link1", "link2", "link3"]
    source.band2_state = {"selected_display_keys": ["reviewee.name"]}
    source.starts_new_page = True
    source.responses_visible_when_closed = True
    source.accepting_responses = True
    db.get(SessionRuleSet, source.rule_set_id).exclude_self_reviews = True
    db.commit()
    assert source.rule_set_id is not None

    replica = instruments.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )

    original = db.get(SessionRuleSet, source.rule_set_id)
    clone = db.get(SessionRuleSet, replica.rule_set_id)
    assert clone.id != original.id
    assert clone.rules_json == original.rules_json
    assert clone.combinator == original.combinator
    assert clone.exclude_self_reviews is True
    assert replica.short_label == "Peer"
    assert replica.band1_touched_links == ["link1", "link2", "link3"]
    assert replica.band2_state == {"selected_display_keys": ["reviewee.name"]}
    assert replica.responses_visible_when_closed is True
    assert replica.accepting_responses is True
    assert replica.starts_new_page is False
    created = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "session_rule_set.created",
        )
    ).scalars().all()
    assert [e.detail["refs"]["session_rule_set_id"] for e in created][-1] == (
        replica.rule_set_id
    )


def test_replicate_repoints_sort_and_widths_at_its_own_fields(
    db: Session,
) -> None:
    review_session, source, op = _setup(db)
    src_displays = _ids(db, InstrumentDisplayField, source.id)
    src_fields = _ids(db, InstrumentResponseField, source.id)
    assert src_displays and src_fields
    source.sort_display_fields = [
        {"display_field_id": src_displays[0], "dir": "desc"}
    ]
    source.column_widths = {
        "identity": 200,
        f"df_{src_displays[0]}": 150,
        f"rf_{src_fields[0]}": 90,
    }
    db.commit()

    replica = instruments.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )

    new_displays = _ids(db, InstrumentDisplayField, replica.id)
    new_fields = _ids(db, InstrumentResponseField, replica.id)
    assert replica.sort_display_fields == [
        {"display_field_id": new_displays[0], "dir": "desc"}
    ]
    assert replica.column_widths == {
        "identity": 200,
        f"df_{new_displays[0]}": 150,
        f"rf_{new_fields[0]}": 90,
    }
    # The source keeps its own ids.
    db.refresh(source)
    assert source.sort_display_fields[0]["display_field_id"] == src_displays[0]


def test_editing_the_replica_band1_leaves_the_source_alone(db: Session) -> None:
    """Guards the cloning choice: a shared row would carry the edit
    into the source."""
    review_session, source, op = _setup(db)
    replica = instruments.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )
    before = list(db.get(SessionRuleSet, source.rule_set_id).rules_json or [])

    instruments.set_band1_assignment_rules(
        db,
        instrument=replica,
        link1_mode="filter",
        link1_combinator="ALL_OF",
        link1_rules=[
            {"field": "reviewer.tag1", "op": "IS", "operand_value": "Lead"}
        ],
        link2_mode="all",
        link2_combinator="ALL_OF",
        link2_rules=[],
        actor=op,
    )
    db.commit()

    assert db.get(SessionRuleSet, source.rule_set_id).rules_json == before
    assert db.get(SessionRuleSet, replica.rule_set_id).rules_json != before


def test_replicate_tolerates_malformed_imported_sort_and_widths(
    db: Session,
) -> None:
    """Settings import stores both columns from unchecked JSON; a shape
    the writers never produce is dropped rather than failing Replicate."""
    review_session, source, op = _setup(db)
    source.sort_display_fields = [5, {"display_field_id": [1]}, {"display_field_id": "3"}]
    source.column_widths = [1, 2]
    db.commit()

    replica = instruments.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )

    assert replica.sort_display_fields == []
    assert replica.column_widths is None


def test_replicate_keeps_the_group_identity_sort(db: Session) -> None:
    """A group instrument's sort by its composed Group column is the
    ``GROUP_IDENTITY_SORT_KEY`` sentinel, not a field id; it carries
    over unchanged."""
    review_session, source, op = _setup(db)
    source.sort_display_fields = [
        {"display_field_id": instruments.GROUP_IDENTITY_SORT_KEY, "dir": "asc"}
    ]
    db.commit()

    replica = instruments.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )

    assert replica.sort_display_fields == [
        {"display_field_id": instruments.GROUP_IDENTITY_SORT_KEY, "dir": "asc"}
    ]
