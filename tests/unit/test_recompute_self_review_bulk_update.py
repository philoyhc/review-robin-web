"""Unit coverage for Segment 19S Item 3 rung 2 — the self-review
recompute reads column tuples and writes one bulk statement.

``recompute_self_review_classification`` runs once per instrument
inside a regenerate and used to select the whole session as
``(Assignment, Reviewer, Reviewee)`` entities, mutating one boolean on
each. At the 200 x 200 bench that is 80,000 ``Assignment`` objects per
call (``guide/app_responsiveness.md`` Finding 4). It now selects the
``AssignmentPair`` projection and writes the changed rows as one ORM
bulk UPDATE keyed by primary key.

Three properties have to survive that, and each has a test here:

1. **Same answer.** The classification and the ``changed`` count match
   an entity-shaped reference implementation, computed independently in
   this module, on a **group-scoped** instrument — the shape where the
   whole-group rule makes the two branches of the rule differ. The
   count is the half that needs the stored flag in the projection; the
   classification is the half that needs the ``Reviewee``.
2. **No ``Assignment`` entity is built.** This is the point of the
   change, and it is what the first draft of this module got wrong: it
   asserted *one UPDATE statement rather than one per row*, which the
   pre-19S code already satisfied — SQLAlchemy's unit of work batches
   same-shape UPDATEs into one executemany, so all six tests here
   passed against a full revert of both rungs (found by the item's cold
   read). The statement count is still asserted, as a guard against a
   future per-row rewrite, but the discriminating assertion is the
   entity-load count.
3. **The identity map keeps up.** ``verify_self_review_classification``
   still reads entities, so a bulk UPDATE that left an already-loaded
   ``Assignment`` stale would make it report drift that is not there.
   SQLAlchemy is pinned only as ``sqlalchemy>=2.0`` in
   ``pyproject.toml``, so this is asserted rather than assumed: an
   upgrade that stops synchronizing the ORM bulk-UPDATE-by-primary-key
   form fails here instead of in the regenerate path.
"""
from __future__ import annotations

from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.assignments import (
    is_self_review,
    recompute_self_review_classification,
    verify_self_review_classification,
)
from app.services.instruments import (
    encode_group_kind,
    ensure_default_instrument,
)
from app.services.responses import group_keys


def _seed_group_scoped(db: Session) -> tuple[ReviewSession, Instrument]:
    """Two reviewers over a tag_1-bounded group-scoped instrument.

    Group ``X`` = {Alice, Bob}, group ``Y`` = {Carol}. Alice is both a
    reviewer and a member of ``X``, so under the whole-group rule
    *every* Alice-about-X row is a self-review — including her row
    about Bob, which no pair-level test would flag. Dave reviews the
    same groups and is a member of neither.
    """
    user = User(email="op@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Groups", code="grp-recompute", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    dave_r = Reviewer(
        session_id=review_session.id, name="Dave", email="dave@example.edu"
    )
    reviewees = [
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
            tag_1="X",
        ),
        Reviewee(
            session_id=review_session.id,
            name="Bob",
            email_or_identifier="bob@example.edu",
            tag_1="X",
        ),
        Reviewee(
            session_id=review_session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
            tag_1="Y",
        ),
    ]
    db.add_all([alice_r, dave_r, *reviewees])
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    instrument.group_kind = encode_group_kind([("reviewee", "tag_1")])
    db.flush()
    for reviewer in (alice_r, dave_r):
        for reviewee in reviewees:
            db.add(
                Assignment(
                    session_id=review_session.id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewee.id,
                    instrument_id=instrument.id,
                    include=True,
                    created_by_mode="rule_based",
                )
            )
    db.flush()
    return review_session, instrument


def _reference_classification(
    db: Session, session_id: int
) -> dict[int, bool]:
    """The pre-19S entity-shaped computation, reproduced here as an
    independent oracle rather than called through the service.

    Deliberately a copy of the shape the recompute used to have —
    ``select(Assignment, Reviewer, Reviewee)``, entity attribute reads,
    ``group_keys`` over ``Assignment`` objects. If the projection
    dropped an attribute the rule needs, this and the service disagree.
    """
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    keys = group_keys(
        db,
        assignments=[assignment for assignment, _, _ in rows],
        session_id=session_id,
    )
    self_group: dict[tuple[int, int], tuple[str, ...]] = {}
    for assignment, reviewer, reviewee in rows:
        if assignment.id in keys and is_self_review(reviewer, reviewee):
            self_group[
                (assignment.instrument_id, assignment.reviewer_id)
            ] = keys[assignment.id]
    out: dict[int, bool] = {}
    for assignment, reviewer, reviewee in rows:
        key = keys.get(assignment.id)
        if key is None:
            out[assignment.id] = is_self_review(reviewer, reviewee)
        else:
            out[assignment.id] = (
                self_group.get(
                    (assignment.instrument_id, assignment.reviewer_id)
                )
                == key
            )
    return out


def _stored_flags(db: Session, session_id: int) -> dict[int, bool]:
    """Stored flags read as column tuples, so the values come from the
    rows rather than from entities the session is holding."""
    return {
        row_id: bool(flag)
        for row_id, flag in db.execute(
            select(Assignment.id, Assignment.is_self_review).where(
                Assignment.session_id == session_id
            )
        ).all()
    }


def test_projection_gives_the_same_answer_as_the_entity_version(
    db: Session,
) -> None:
    """Classification and ``changed`` count both match the entity
    reference on a group-scoped instrument."""
    review_session, _ = _seed_group_scoped(db)
    expected = _reference_classification(db, review_session.id)

    # Every row starts at the column default, so the expected number of
    # changed rows is the number the reference says are self-reviews.
    assert set(_stored_flags(db, review_session.id).values()) == {False}
    changed = recompute_self_review_classification(
        db, session_id=review_session.id
    )

    assert changed == sum(expected.values()) > 0, (
        "the count came from the stored flag in the projection"
    )
    assert _stored_flags(db, review_session.id) == expected

    # The whole-group rule, spelled out so a regression that collapses
    # it to the pair-level test is legible rather than just a count
    # mismatch: all three of Alice's rows about group X and Y are
    # decided by membership, Dave's by nothing.
    flagged = {
        (reviewer_name, reviewee_name)
        for reviewer_name, reviewee_name, flag in db.execute(
            select(Reviewer.name, Reviewee.name, Assignment.is_self_review)
            .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
            .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
            .where(Assignment.session_id == review_session.id)
        ).all()
        if flag
    }
    assert flagged == {("Alice", "Alice"), ("Alice", "Bob")}, (
        "Alice's row about Bob is a self-review because she is a member "
        "of the group she is reviewing; her row about Carol is not"
    )

    # Idempotent: nothing left to change, and the count says so.
    assert recompute_self_review_classification(
        db, session_id=review_session.id
    ) == 0


def test_recompute_builds_no_assignment_entities(db: Session) -> None:
    """The recompute materializes no ``Assignment`` and no ``Reviewer``,
    and one ``Reviewee`` per reviewee rather than one per row.

    The discriminating test for rung 2: the pre-19S recompute selected
    ``(Assignment, Reviewer, Reviewee)`` and loads **6** ``Assignment``
    plus **2** ``Reviewer`` entities on this fixture, where the
    projection loads none of either. Counted through the ORM ``load``
    event, which fires once per entity actually constructed from a row
    — not through the identity map, which holds weak references and so
    reports zero either way once the rows go out of scope.

    The ``Reviewee`` count is the other half: 3 for 6 rows is the
    primary-key dedupe that ``AssignmentPair`` relies on when it keeps
    the reviewee as an entity, so a session's reviewee count bounds the
    instances however many assignments join to them.
    """
    review_session, _ = _seed_group_scoped(db)
    db.flush()

    loads = {"Assignment": 0, "Reviewer": 0, "Reviewee": 0}

    def _counter(name: str):  # type: ignore[no-untyped-def]
        def handler(target, context):  # type: ignore[no-untyped-def]
            loads[name] += 1

        return handler

    handlers = [
        (Assignment, _counter("Assignment")),
        (Reviewer, _counter("Reviewer")),
        (Reviewee, _counter("Reviewee")),
    ]
    for entity, handler in handlers:
        event.listen(entity, "load", handler)
    try:
        changed = recompute_self_review_classification(
            db, session_id=review_session.id
        )
    finally:
        for entity, handler in handlers:
            event.remove(entity, "load", handler)

    assert changed == 2, "Alice's two rows about her own group"
    assert loads["Assignment"] == 0, (
        "the projection replaced the Assignment entities — the pre-19S "
        f"version loads 6 here, this loaded {loads['Assignment']}"
    )
    assert loads["Reviewer"] == 0, "Reviewer.email is projected as a scalar"
    assert loads["Reviewee"] == 3, (
        "one Reviewee instance per reviewee, not per assignment row "
        f"(6 rows, 3 reviewees, {loads['Reviewee']} loaded)"
    )


def test_changed_rows_go_out_as_one_statement(
    db: Session, engine: Engine
) -> None:
    """The write is one bulk UPDATE, not one per changed row — and a
    recompute with nothing to change issues none.

    Not a discriminating test: the entity-mutation loop this replaced
    also issued one statement, because the unit of work batches
    same-shape UPDATEs. It stands as a regression guard against a
    future rewrite that loops per row, which is the plausible way to
    lose this.
    """
    review_session, _ = _seed_group_scoped(db)

    updates: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, many):  # type: ignore[no-untyped-def]
        if "UPDATE assignments" in statement.replace("\n", " "):
            updates.append(statement)

    try:
        changed = recompute_self_review_classification(
            db, session_id=review_session.id
        )
        assert changed == 2, "Alice's two rows about her own group"
        assert len(updates) == 1, (
            f"one bulk statement for {changed} rows, got {len(updates)}"
        )

        updates.clear()
        assert recompute_self_review_classification(
            db, session_id=review_session.id
        ) == 0
        assert updates == [], "a no-op recompute writes nothing"
    finally:
        event.remove(engine, "before_cursor_execute", _record)


def test_bulk_update_keeps_loaded_entities_in_step(db: Session) -> None:
    """An ``Assignment`` the session already holds sees the new value
    without a reload, so the entity-shaped
    ``verify_self_review_classification`` reports no drift.

    This pins SQLAlchemy's ORM bulk-UPDATE-by-primary-key
    synchronization, which the version pin (``>=2.0``) does not. If it
    ever stops holding, the recompute needs an explicit expiry and
    this test is where that shows up — rather than as an
    ``AssertionError`` out of the regenerate path.
    """
    review_session, _ = _seed_group_scoped(db)
    loaded = {
        assignment.id: assignment
        for assignment in db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    }
    assert loaded and not any(a.is_self_review for a in loaded.values())

    recompute_self_review_classification(db, session_id=review_session.id)

    stored = _stored_flags(db, review_session.id)
    assert {
        row_id: assignment.is_self_review
        for row_id, assignment in loaded.items()
    } == stored, "loaded entities agree with the rows"
    assert verify_self_review_classification(
        db, session_id=review_session.id
    ) == []
