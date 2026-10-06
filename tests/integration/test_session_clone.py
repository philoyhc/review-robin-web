"""Coverage for ``app.services.session_clone`` and the lobby clone
route — Segment 18A Part 1 session cloning."""
from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    DataShape,
    Instrument,
    InstrumentResponseField,
    Observer,
    Relationship,
    ReviewSession,
    Reviewee,
    Reviewer,
    User,
)
from app.schemas.sessions import SessionCreate
from app.services import session_clone, session_tags, sessions


def _source_session(db: Session, code: str) -> tuple[ReviewSession, User]:
    """A session with the create-time seed config plus a one-pair
    roster and a tag — a realistic clone source."""
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = sessions.create_session(
        db, user=op, payload=SessionCreate(name=code.title(), code=code)
    )
    reviewer = Reviewer(
        session_id=review_session.id, name="R One", email="r1@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="E One",
        email_or_identifier="e1@example.edu",
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            status="active",
        )
    )
    db.commit()
    session_tags.add_tag(
        db, review_session=review_session, user=op, tag="pilot"
    )
    return review_session, op


def test_clone_all_copies_full_graph(db: Session) -> None:
    source, op = _source_session(db, "clone-all")

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )

    assert clone.id != source.id
    assert clone.name == "Copy of Clone-All"
    assert clone.code != source.code
    assert clone.status == "draft"
    assert clone.deadline is None
    assert clone.created_by_user_id == op.id

    # Roster copied, with relationship FKs re-pointed at the clones.
    clone_reviewers = db.execute(
        select(Reviewer).where(Reviewer.session_id == clone.id)
    ).scalars().all()
    clone_reviewees = db.execute(
        select(Reviewee).where(Reviewee.session_id == clone.id)
    ).scalars().all()
    clone_rels = db.execute(
        select(Relationship).where(Relationship.session_id == clone.id)
    ).scalars().all()
    assert len(clone_reviewers) == 1
    assert len(clone_reviewees) == 1
    assert len(clone_rels) == 1
    assert clone_rels[0].reviewer_id == clone_reviewers[0].id
    assert clone_rels[0].reviewee_id == clone_reviewees[0].id

    # Config copied; tags copied in every mode.
    assert db.execute(
        select(Instrument).where(Instrument.session_id == clone.id)
    ).scalars().all()
    assert session_tags.tags_for_sessions(db, [clone.id])[clone.id] == [
        "pilot"
    ]


def test_clone_copies_data_shapes_retention_and_toggles(db: Session) -> None:
    """18P PR D1 — clone carries the feature toggles, retention config,
    and saved Data shapes (scope chips re-pointed at the clone), while
    the schedule resets by design."""
    source, op = _source_session(db, "clone-d1")
    source.relationships_enabled = True
    source.observers_enabled = True
    source.retention_exception = True
    source.retention_overrides = {"audit_log_days": 365}
    # A scheduling anchor that must NOT survive the clone.
    source.scheduled_activate_at = dt.datetime(
        2026, 6, 1, 9, 0, tzinfo=dt.timezone.utc
    )
    db.flush()

    src_inst = db.execute(
        select(Instrument).where(Instrument.session_id == source.id)
    ).scalars().first()
    src_rf = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == src_inst.id
        )
    ).scalars().first()
    db.add(
        DataShape(
            session_id=source.id,
            name="My shape",
            axis="reviewer",
            instrument_id=src_inst.id,
            response_field_id=src_rf.id,
            column_chip_slots="[]",
            created_by_user_id=op.id,
        )
    )
    db.commit()

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="config"
    )
    db.refresh(clone)

    assert clone.relationships_enabled is True
    assert clone.observers_enabled is True
    assert clone.retention_exception is True
    assert clone.retention_overrides == {"audit_log_days": 365}
    # Schedule resets by design.
    assert clone.scheduled_activate_at is None

    clone_shapes = db.execute(
        select(DataShape).where(DataShape.session_id == clone.id)
    ).scalars().all()
    assert len(clone_shapes) == 1
    shape = clone_shapes[0]
    assert shape.name == "My shape"

    clone_inst = db.execute(
        select(Instrument).where(Instrument.session_id == clone.id)
    ).scalars().first()
    clone_rf = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == clone_inst.id
        )
    ).scalars().first()
    # Scope chips re-pointed at the clone's rows, not the source's.
    assert shape.instrument_id == clone_inst.id
    assert shape.response_field_id == clone_rf.id
    assert shape.instrument_id != src_inst.id


def test_clone_all_does_not_copy_results_acknowledgement(
    db: Session,
) -> None:
    """A reviewee's acknowledgement is of the source session's results,
    so the cloned reviewee starts unacknowledged (D14)."""
    source, op = _source_session(db, "clone-ack")
    source_reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == source.id)
    ).scalar_one()
    source_reviewee.results_acknowledged_at = dt.datetime(
        2026, 9, 1, 9, 0, tzinfo=dt.timezone.utc
    )
    db.commit()

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )

    clone_reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == clone.id)
    ).scalar_one()
    assert clone_reviewee.email_or_identifier == "e1@example.edu"
    assert clone_reviewee.results_acknowledged_at is None
    db.refresh(source_reviewee)
    assert source_reviewee.results_acknowledged_at is not None


def test_clone_all_copies_observers_with_their_cohort_rules(
    db: Session,
) -> None:
    """Duplicate copies every roster, observers included (author's
    ruling, 2026-10-02), each with its status, tag and cohort rule."""
    source, op = _source_session(db, "clone-obs")
    rule = {
        "combinator": "AND",
        "rules": [
            {"field": "reviewee.tag1", "op": "IS THE SAME AS",
             "operand_tag": "observer.tag1", "operand_value": ""}
        ],
    }
    db.add(
        Observer(
            session_id=source.id,
            email="obs@example.edu",
            display_name="Obs",
            status="inactive",
            tag_1="north",
            cohort_rule=rule,
        )
    )
    db.commit()

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )

    clone_observer = db.execute(
        select(Observer).where(Observer.session_id == clone.id)
    ).scalar_one()
    assert (
        clone_observer.email,
        clone_observer.display_name,
        clone_observer.status,
        clone_observer.tag_1,
    ) == ("obs@example.edu", "Obs", "inactive", "north")
    assert clone_observer.cohort_rule == rule
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.cloned",
            AuditEvent.session_id == clone.id,
        )
    ).scalar_one()
    assert event.detail["counts"]["observers"] == 1


def test_clone_config_skips_roster(db: Session) -> None:
    source, op = _source_session(db, "clone-config")
    db.add(Observer(session_id=source.id, email="obs-cfg@example.edu"))
    db.commit()

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="config"
    )

    assert (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == clone.id)
        ).scalars().all()
        == []
    )
    assert (
        db.execute(
            select(Relationship).where(Relationship.session_id == clone.id)
        ).scalars().all()
        == []
    )
    assert (
        db.execute(
            select(Observer).where(Observer.session_id == clone.id)
        ).scalars().all()
        == []
    )
    # Config + tags still copied.
    assert db.execute(
        select(Instrument).where(Instrument.session_id == clone.id)
    ).scalars().all()
    assert session_tags.tags_for_sessions(db, [clone.id])[clone.id] == [
        "pilot"
    ]


def test_clone_writes_audit_event(db: Session) -> None:
    source, op = _source_session(db, "clone-audit")

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.cloned",
            AuditEvent.session_id == clone.id,
        )
    ).scalar_one()
    assert event.detail["context"]["mode"] == "all"
    assert event.detail["refs"]["source_session_id"] == source.id
    assert event.detail["counts"]["observers"] == 0


def test_clone_derives_a_unique_code(db: Session) -> None:
    source, op = _source_session(db, "clone-dup")

    first = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )
    second = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )

    assert first.code != second.code


def test_clone_route_redirects_to_the_clone(
    client: TestClient, db: Session
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Routed", "code": "clone-route"},
        follow_redirects=False,
    )
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "clone-route")
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{session_id}/clone",
        data={"mode": "all"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    # 18R Item 4 Slice 5 — clone redirects to Session Home with the Session
    # details card open in edit mode so the operator can rename the clone
    # immediately (the Edit page is retired).
    assert location.startswith("/operator/sessions/")
    assert location.endswith("?editing=1#session-config")
    clone_id = int(
        location.split("/operator/sessions/")[1].split("?")[0]
    )
    assert clone_id != session_id
    clone = db.get(ReviewSession, clone_id)
    assert clone.name == "Copy of Routed"


def test_a_clone_starts_with_no_assignment_mode(db: Session) -> None:
    """A clone carries no assignments, so it carries no mode. 19N.

    ``assignment_mode`` records *how this session's assignments were
    produced*, and the codebase treats ``None`` as "never Generated":
    ``replace_assignments`` sets it, deleting every assignment clears it
    back to ``None`` (`_coverage.py`), and **three validation rules skip
    on ``None``** to avoid doubling the "no pairs" warnings with
    every-reviewer-missing noise.

    A clone copies no ``Assignment`` rows, so copying the source's mode
    broke that invariant: the clone claimed a generation that never
    happened, and the three rules ran on it instead of skipping. It also
    propagated a legacy ``manual`` value — retired in 16A PR 5 — into
    newly created sessions, which is how `SC-41` was found.
    """
    source, op = _source_session(db, "clone-mode")
    source.assignment_mode = "rule_based"
    db.flush()

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )
    db.flush()

    assert clone.assignment_mode is None, (
        "a clone has no assignments, so it must not claim a mode — "
        "None is the codebase's marker for 'never Generated'"
    )


def test_a_clone_does_not_trip_the_never_generated_rules(
    db: Session,
) -> None:
    """The consequence of the invariant, not just the invariant.

    ``assignments.reviewer_missing`` skips when ``assignment_mode is
    None``; its docstring says surfacing every-reviewer-missing on top of
    the no-pairs warnings would "double up the noise". A clone with a
    copied mode defeated that skip on a session that has, by
    construction, no assignments at all.
    """
    from app.services.validation import validate_session_setup

    source, op = _source_session(db, "clone-noise")
    source.assignment_mode = "rule_based"
    db.flush()

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )
    db.flush()

    keys = {
        issue.rule_key
        for issue in validate_session_setup(db, clone)
        if getattr(issue, "rule_key", None)
    }
    assert "assignments.reviewer_missing" not in keys, (
        "the clone has no assignments, so the never-Generated skip "
        "should suppress this rule"
    )


def test_a_clone_repoints_sort_and_widths_at_its_own_fields(
    db: Session,
) -> None:
    """Findings A28: the default sort and column widths name fields by
    id. A clone used to copy them verbatim, so they named the source's
    fields and the clone lost its sort and widths. They now name the
    clone's own fields, as Replicate does; the Group sentinel and the
    identity width, which name no field, ride as they are."""
    from app.db.models import InstrumentDisplayField

    source, op = _source_session(db, "clone-refs")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == source.id)
    ).scalar_one()
    display = InstrumentDisplayField(
        instrument_id=instrument.id, label="", source_type="reviewee",
        source_field="tag_1", order=9, visible=True,
    )
    db.add(display)
    db.flush()
    field = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .order_by(InstrumentResponseField.order)
    ).scalars().first()
    instrument.sort_display_fields = [
        {"display_field_id": display.id, "dir": "desc"},
        {"display_field_id": -1, "dir": "asc"},
    ]
    instrument.column_widths = {
        "identity": 210,
        f"df_{display.id}": 140,
        f"rf_{field.id}": 90,
    }
    db.commit()

    clone = session_clone.clone_session(db, source=source, user=op, mode="all")

    copy = db.execute(
        select(Instrument).where(Instrument.session_id == clone.id)
    ).scalar_one()
    copy_display = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == copy.id,
            InstrumentDisplayField.source_field == "tag_1",
        )
    ).scalar_one()
    copy_field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == copy.id,
            InstrumentResponseField.field_key == field.field_key,
        )
    ).scalar_one()
    assert copy.sort_display_fields == [
        {"display_field_id": copy_display.id, "dir": "desc"},
        {"display_field_id": -1, "dir": "asc"},
    ]
    assert copy.column_widths == {
        "identity": 210,
        f"df_{copy_display.id}": 140,
        f"rf_{copy_field.id}": 90,
    }
    assert copy_display.id != display.id


def test_a_clone_drops_a_width_naming_another_instruments_field(
    db: Session,
) -> None:
    """Each instrument's widths re-point against its own fields only, as
    Replicate's do: a stray ``rf_<id>`` naming an earlier instrument's
    field is dropped, not re-pointed at that field's clone."""
    source, op = _source_session(db, "clone-stray")
    first = db.execute(
        select(Instrument).where(Instrument.session_id == source.id)
    ).scalar_one()
    first_field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == first.id
        )
    ).scalars().first()
    second = Instrument(
        session_id=source.id,
        name="Second",
        order=first.order + 1,
        column_widths={"identity": 180, f"rf_{first_field.id}": 70},
    )
    db.add(second)
    db.commit()

    clone = session_clone.clone_session(db, source=source, user=op, mode="all")

    copy = db.execute(
        select(Instrument).where(
            Instrument.session_id == clone.id, Instrument.name == "Second"
        )
    ).scalar_one()
    assert copy.column_widths == {"identity": 180}


def test_a_clone_copies_each_instruments_visibility_grid(db: Session) -> None:
    """G5 (ruled 2026-10-06): Duplicate copies the visibility grid, as
    Replicate does, in both modes — each instrument's onto its own copy,
    one ``instrument.view_policy_set`` per row under the request's
    correlation id. The schedule still resets on purpose."""
    from app.services import visibility_policies as vp

    source, op = _source_session(db, "clone-vis")
    first = db.execute(
        select(Instrument).where(Instrument.session_id == source.id)
    ).scalar_one()
    second = Instrument(session_id=source.id, name="Second", order=first.order + 1)
    db.add(second)
    db.flush()
    cells = {
        first.name: [
            ("reviewee", None, "anonymized"),
            ("observer", "summarized", "raw"),
        ],
        "Second": [("observer", None, "summarized")],
    }
    for instrument in (first, second):
        for audience, ongoing, after in cells[instrument.name]:
            vp.upsert_policy(
                db,
                review_session=source,
                instrument=instrument,
                audience=audience,
                while_ongoing_mode=ongoing,
                after_release_mode=after,
                user=op,
            )
    now = dt.datetime(2026, 10, 6, 9, 0, tzinfo=dt.timezone.utc)
    source.deadline = now + dt.timedelta(days=7)
    source.responses_release_at = now + dt.timedelta(days=8)
    source.responses_release_until = now + dt.timedelta(days=20)
    source.invite_offsets = ["-PT48H"]
    source.reminder_offsets = ["-PT24H"]
    source.archive_offset = "PT24H"
    db.commit()

    def grids(session_id: int) -> dict[str, dict[str, tuple[str | None, str | None]]]:
        out: dict[str, dict[str, tuple[str | None, str | None]]] = {}
        for instrument in db.execute(
            select(Instrument).where(Instrument.session_id == session_id)
        ).scalars():
            out[instrument.name] = {
                audience: tuple(
                    vp.decode_mode(
                        getattr(policy, f"{w}_granularity"),
                        getattr(policy, f"{w}_identification"),
                    )
                    if getattr(policy, f"{w}_granularity") is not None
                    else None
                    for w in ("while_ongoing", "after_release")
                )
                for audience, policy in vp.list_for_instrument(
                    db, instrument.id
                ).items()
            }
        return out

    expected = grids(source.id)
    assert expected == {
        name: {audience: (ongoing, after) for audience, ongoing, after in rows}
        for name, rows in cells.items()
    }
    for mode in ("all", "config"):
        clone = session_clone.clone_session(
            db, source=source, user=op, mode=mode, correlation_id=f"cid-{mode}"
        )
        assert grids(clone.id) == expected, mode
        events = db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "instrument.view_policy_set",
                AuditEvent.session_id == clone.id,
            )
        ).scalars().all()
        assert len(events) == 3, mode
        assert {e.correlation_id for e in events} == {f"cid-{mode}"}, mode
        assert clone.deadline is None
        assert clone.responses_release_at is None
        assert clone.responses_release_until is None
        assert not clone.invite_offsets
        assert not clone.reminder_offsets
        assert clone.archive_offset is None
