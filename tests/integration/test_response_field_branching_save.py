"""19T Item 10 rung 2 — branches stored on response fields hold to the
branching rules through every way the Instruments page saves a field.

No page authors a branch yet (the builder rung does), so each test builds
one directly: Rating (Integer) is the parent, with the condition
``ge 4``, and Comments is the field it governs."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)

from .test_instrument_builder_routes import _band2_rfs, _new_model_with_tags


def _branched(
    client: TestClient, db: Session, code: str
) -> tuple[ReviewSession, Instrument, InstrumentResponseField, InstrumentResponseField]:
    review_session, instrument = _new_model_with_tags(client, db, code=code)
    fields = {f.label: f for f in instrument.response_fields}
    rating, comments = fields["Rating"], fields["Comments"]
    assert comments.order == rating.order + 1
    rating.branch_op, rating.branch_value = "ge", "4"
    comments.branch_parent_id = rating.id
    db.commit()
    return review_session, instrument, rating, comments


def _save(client: TestClient, review_session, instrument, rfs: list[dict]):
    return client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{instrument.id}/save",
        data={"band2_state_snapshot": json.dumps(
            {"selected_display_keys": [], "response_fields": rfs}
        )},
        follow_redirects=False,
    )


def _rfs(instrument: Instrument, **changes: dict) -> list[dict]:
    """The card's payload for ``instrument``, with per-label changes."""
    out = []
    for rf in _band2_rfs(instrument):
        change = changes.get(rf["name"], {})
        if change is None:
            continue
        out.append({**rf, **change})
    return out


def _add_response(db: Session, review_session, instrument, field) -> None:
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalars().first()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars().first()
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()
    db.add(Response(assignment_id=assignment.id, response_field_id=field.id, value="x"))
    db.commit()


def test_a_save_that_leaves_the_branch_alone_keeps_it(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, rating, comments = _branched(client, db, "19t10-keep")
    response = _save(client, review_session, instrument, _rfs(instrument))
    assert response.status_code == 200, response.text
    db.expire_all()
    assert (rating.branch_op, rating.branch_value) == ("ge", "4")
    assert comments.branch_parent_id == rating.id


def test_a_save_creates_a_branch_by_row_key(
    client: TestClient, db: Session
) -> None:
    """The stager names a governed field's parent by row key, so one Save
    can create both (the builder's ⑂)."""
    review_session, instrument = _new_model_with_tags(client, db, code="19t10-keys")
    rfs = _rfs(instrument)
    rfs = [{**rf, "row_key": f"rf_{i}"} for i, rf in enumerate(rfs)]
    rfs += [
        {"name": "Score", "data_type": "integer", "min": "1", "max": "5",
         "row_key": "rf_9", "branch_op": "le", "branch_value": "2",
         "branch_parent": None, "selected": True},
        {"name": "Why low", "data_type": "string", "row_key": "rf_10",
         "branch_parent": "rf_9", "branch_op": None, "branch_value": None,
         "selected": True},
    ]
    response = _save(client, review_session, instrument, rfs)
    assert response.status_code == 200, response.text
    db.expire_all()
    fields = {f.label: f for f in instrument.response_fields}
    assert (fields["Score"].branch_op, fields["Score"].branch_value) == ("le", "2")
    assert fields["Why low"].branch_parent_id == fields["Score"].id
    events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.field_updated")
    ).scalars().all()
    assert {e.detail["context"]["field_key"]: e.detail["changes"] for e in events} == {
        fields["Score"].field_key: {"branch_op": [None, "le"], "branch_value": [None, "2"]},
        fields["Why low"].field_key: {"branch_parent_id": [None, fields["Score"].id]},
    }


def test_a_saved_field_can_join_a_branch_and_leave_it(
    client: TestClient, db: Session
) -> None:
    """Rung 7b's ↳ and ↰ are membership changes to fields that already
    exist; with no responses, Save takes both."""
    review_session, instrument = _new_model_with_tags(client, db, code="19t10-join2")
    keyed = [{**rf, "row_key": f"rf_{i}"} for i, rf in enumerate(_rfs(instrument))]
    parent_key = next(rf["row_key"] for rf in keyed if rf["name"] == "Rating")
    joined = [
        {**rf, "branch_op": "ge", "branch_value": "4"} if rf["name"] == "Rating"
        else {**rf, "branch_parent": parent_key, "required": False}
        if rf["name"] == "Comments" else rf
        for rf in keyed
    ]
    response = _save(client, review_session, instrument, joined)
    assert response.status_code == 200, response.text
    db.expire_all()
    fields = {f.label: f for f in instrument.response_fields}
    assert fields["Comments"].branch_parent_id == fields["Rating"].id
    detached = [
        {**rf, "branch_parent": None, "branch_op": None, "branch_value": None}
        for rf in joined
    ]
    response = _save(client, review_session, instrument, detached)
    assert response.status_code == 200, response.text
    db.expire_all()
    assert all(
        (f.branch_parent_id, f.branch_op) == (None, None)
        for f in instrument.response_fields
    )


def test_the_branch_keys_are_checked(client: TestClient, db: Session) -> None:
    """Each case on an instrument of its own: a refused save's flushed
    writes are rolled back by the request in production, not by the
    test's shared session."""
    cases = [
        ({"Comments": {"branch_parent": "rf_99"}},
         "Comments: Its branch's parent field is missing."),
        ({"Rating": {"branch_op": "ge", "branch_value": "x"},
          "Comments": {"branch_parent": "parent"}},
         "Rating: The branch condition needs a number."),
        ({"Rating": {"branch_op": "ge", "branch_value": "4"}},
         "Rating: Its branch condition governs no field."),
    ]
    for n, (changes, error) in enumerate(cases):
        review_session, instrument = _new_model_with_tags(
            client, db, code=f"19t10-bad-{n}"
        )
        rfs = []
        for i, rf in enumerate(_rfs(instrument)):
            rf = {**rf, "row_key": "parent" if rf["name"] == "Rating" else f"rf_{i}"}
            rfs.append({**rf, **changes.get(rf["name"], {})})
        response = _save(client, review_session, instrument, rfs)
        assert response.status_code == 422, error
        assert response.json()["errors"] == [error]


def test_a_hidden_parent_hides_its_branch(client: TestClient, db: Session) -> None:
    """The Active cascade, held by the service as well as the card."""
    review_session, instrument, rating, comments = _branched(client, db, "19t10-hide")
    response = _save(
        client, review_session, instrument,
        _rfs(instrument, Rating={"selected": False}, Comments={"selected": True}),
    )
    assert response.status_code == 200, response.text
    db.expire_all()
    assert (rating.visible, comments.visible) == (False, False)


def test_a_parent_with_a_branch_cannot_be_deleted(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, rating, _ = _branched(client, db, "19t10-parent")
    response = _save(client, review_session, instrument, _rfs(instrument, Rating=None))
    assert response.status_code == 422
    assert response.json()["errors"] == ["Rating: Delete its branch first."]


def test_deleting_the_last_governed_field_deletes_the_condition(
    client: TestClient, db: Session
) -> None:
    """A branch is its condition plus at least one field, so the last
    field's X takes the condition with it."""
    review_session, instrument, rating, comments = _branched(client, db, "19t10-last")
    comments_id = comments.id
    response = _save(client, review_session, instrument, _rfs(instrument, Comments=None))
    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(InstrumentResponseField, comments_id) is None
    assert (rating.branch_op, rating.branch_value) == (None, None)
    # The cleared condition is audited on the parent (Codex on #2639).
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instrument.field_updated")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["changes"] == {
        "branch_op": ["ge", None], "branch_value": ["4", None]
    }
    assert event.detail["refs"]["response_field_id"] == rating.id


def test_deleting_a_parent_with_its_whole_branch_in_one_save_is_bottom_up(
    client: TestClient, db: Session
) -> None:
    """Deleting the last governed field and then the parent in one edit is
    the bottom-up order the builder allows: once the branch is gone the
    parent's X comes back, so one Save sends neither."""
    review_session, instrument, rating, comments = _branched(client, db, "19t10-both")
    ids = (rating.id, comments.id)
    response = _save(
        client, review_session, instrument,
        _rfs(instrument, Rating=None, Comments=None),
    )
    assert response.status_code == 200, response.text
    db.expire_all()
    assert all(db.get(InstrumentResponseField, i) is None for i in ids)


def test_governed_answers_lock_the_branch_fields(
    client: TestClient, db: Session
) -> None:
    """Once a governed field has responses, none of the branch's fields
    can go, not only the answered one."""
    review_session, instrument, rating, comments = _branched(client, db, "19t10-lock")
    why = InstrumentResponseField(
        instrument_id=instrument.id, field_key="why", label="Why",
        order=comments.order + 1,
        _inline_data_type="String", branch_parent_id=rating.id,
    )
    db.add(why)
    db.commit()
    _add_response(db, review_session, instrument, comments)
    db.expire_all()
    response = _save(client, review_session, instrument, _rfs(instrument, Why=None))
    assert response.status_code == 422
    assert response.json()["errors"] == [
        "Why: Its branch has saved responses, so the branch's fields can't change."
    ]


def test_governed_answers_lock_the_condition_and_membership(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, rating, comments = _branched(client, db, "19t10-lock2")
    _add_response(db, review_session, instrument, comments)
    db.expire_all()
    keyed = [{**rf, "row_key": f"rf_{i}"} for i, rf in enumerate(_rfs(instrument))]
    parent_key = next(rf["row_key"] for rf in keyed if rf["name"] == "Rating")
    condition = [
        {**rf, "branch_value": "3"} if rf["name"] == "Rating" else rf for rf in keyed
    ]
    at = next(i for i, rf in enumerate(keyed) if rf["name"] == "Comments") + 1
    joined = keyed[:at] + [
        {"name": "More", "data_type": "string", "row_key": "rf_99",
         "branch_parent": parent_key}
    ] + keyed[at:]
    for rfs, error in (
        (condition, "Rating: Its branch has saved responses, so its condition "
                    "can't change."),
        (joined, "More: Its branch has saved responses, so the branch's fields "
                 "can't change."),
    ):
        response = _save(client, review_session, instrument, rfs)
        assert response.status_code == 422, error
        assert response.json()["errors"] == [error]
        db.expire_all()


def test_an_answered_field_cannot_move_into_a_branch(
    client: TestClient, db: Session
) -> None:
    """Its answers could then sit in a closed branch."""
    review_session, instrument = _new_model_with_tags(client, db, code="19t10-join")
    comments = next(f for f in instrument.response_fields if f.label == "Comments")
    _add_response(db, review_session, instrument, comments)
    db.expire_all()
    keyed = [{**rf, "row_key": f"rf_{i}"} for i, rf in enumerate(_rfs(instrument))]
    parent_key = next(rf["row_key"] for rf in keyed if rf["name"] == "Rating")
    rfs = [
        {**rf, "branch_op": "ge", "branch_value": "4"} if rf["name"] == "Rating"
        else {**rf, "branch_parent": parent_key} if rf["name"] == "Comments"
        else rf
        for rf in keyed
    ]
    response = _save(client, review_session, instrument, rfs)
    assert response.status_code == 422
    assert response.json()["errors"] == [
        "Comments: It has saved responses, so it can't move into a branch."
    ]


def test_parent_answers_alone_do_not_lock_the_branch(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, rating, comments = _branched(client, db, "19t10-parent-ans")
    _add_response(db, review_session, instrument, rating)
    db.expire_all()
    response = _save(client, review_session, instrument, _rfs(instrument, Comments=None))
    assert response.status_code == 200, response.text


def test_the_saved_state_is_checked_against_the_branch_rules(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, *_ = _branched(client, db, "19t10-rules")
    cases = [
        # 19T Item 11 — a required governed field needs an active required
        # field outside the branch, and Rating is the only one.
        (_rfs(instrument, Rating={"required": False}, Comments={"required": True}),
         "Comments: A field inside a branch can be required only when the "
         "instrument has an active required field outside any branch."),
        (_rfs(instrument, Rating={"data_type": "string", "min": "", "max": "",
                                  "step": ""}),
         "Rating: A String field can't have a branch."),
        # A new field inserted between the parent and its branch.
        (_rfs(instrument)[:1] + [{"name": "Notes", "data_type": "string"}]
         + _rfs(instrument)[1:],
         "Rating: A branch's fields must directly follow their parent."),
    ]
    for rfs, error in cases:
        response = _save(client, review_session, instrument, rfs)
        assert response.status_code == 422, error
        assert response.json()["errors"] == [error]
        db.expire_all()


def test_the_per_field_routes_refuse_a_branched_instrument(
    client: TestClient, db: Session
) -> None:
    """Edit, delete, move and insert act on one field and can't keep a
    branch's rules, so they refuse; the card's Save checks it whole."""
    review_session, instrument, rating, comments = _branched(client, db, "19t10-legacy")
    base = f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields"
    for url, data in [
        (f"{base}/{comments.id}/edit", {"label": "Comments", "required": "true"}),
        (f"{base}/{rating.id}/delete", {"confirm": "true"}),
        (f"{base}/{comments.id}/move", {"direction": "up"}),
        (f"{base}/add-row", {"after": str(rating.id)}),
    ]:
        response = client.post(url, data=data, follow_redirects=False)
        assert response.status_code == 409, url
        assert "has branches" in response.text, url
    db.expire_all()
    assert db.get(InstrumentResponseField, rating.id) is not None
    assert comments.required is False


def test_an_instrument_with_a_branch_can_be_deleted(
    client: TestClient, db: Session
) -> None:
    """The parent reference is ``ON DELETE SET NULL``, so deleting the
    instrument's fields in any order passes Postgres's foreign-key check."""
    review_session, instrument, *_ = _branched(client, db, "19t10-delete-inst")
    instrument_id = instrument.id
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument_id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.expire_all()
    assert db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument_id
        )
    ).first() is None


def test_a_session_clone_points_the_branch_at_the_cloned_parent(
    client: TestClient, db: Session
) -> None:
    """Clone copies every column generically; the parent reference is
    re-pointed at the parent's clone rather than the source session's."""
    from app.db.models import User
    from app.services import session_clone

    review_session, instrument, rating, comments = _branched(
        client, db, "19t10-clone"
    )
    user = db.execute(select(User)).scalars().first()
    clone = session_clone.clone_session(
        db, source=review_session, user=user, mode="all"
    )
    db.flush()
    cloned = {
        f.label: f
        for f in db.execute(
            select(InstrumentResponseField)
            .join(Instrument)
            .where(Instrument.session_id == clone.id)
        ).scalars()
        # Only the branched instrument's two fields carry branch columns.
        if f.branch_op or f.branch_parent_id
    }
    assert (cloned["Rating"].branch_op, cloned["Rating"].branch_value) == ("ge", "4")
    assert cloned["Comments"].branch_parent_id == cloned["Rating"].id
    assert cloned["Rating"].id != rating.id


def test_an_unknown_operator_is_refused_by_name(
    client: TestClient, db: Session
) -> None:
    """The cumulative read's finding 3: refused before any flush, so a
    long token never reaches Postgres's ``String(8)`` as a 500."""
    review_session, instrument = _new_model_with_tags(client, db, code="19t10-op")
    rfs = _rfs(instrument, Rating={"branch_op": "greater-than-or-equal"})
    rfs.append({"name": "New", "data_type": "string"})
    response = _save(client, review_session, instrument, rfs)
    assert response.status_code == 422
    assert response.json()["errors"] == [
        "Rating: Choose a comparison for the branch condition."
    ]
