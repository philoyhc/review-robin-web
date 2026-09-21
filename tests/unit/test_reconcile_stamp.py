"""19R Item 2 rung 2 — the reconcile stamp.

The stamp decides when the cached staleness verdict may be served
without running the rules engine, so the only failure that matters is
**two different situations sharing a stamp**: the badge would then say
"fresh" about generated rows that no longer match their rules, which
``app/services/validation.py`` records this signal having once done
already.

So the shape of this file is one case per thing the verdict is derived
from, each asserting the stamp *moves*. The equality tests are the
smaller half, and they are here to stop the whole thing being satisfied
by a function that returns a fresh random value.

Each mutation is applied, stamped, undone, and stamped again — the undo
is asserted, so a case that silently failed to restore cannot make the
next one pass for the wrong reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services.assignments import _reconcile_cache as cache
from app.services.instruments import ensure_default_instrument
from app.services.rules.fields import FIELD_MAP


@dataclass
class Inputs:
    """Everything :func:`reconcile_stamp` reads, held so a case can
    move one part of it and put it back."""

    review_session: ReviewSession
    instrument: Instrument
    session_rule_set: SessionRuleSet | None
    reviewers: list[Reviewer]
    reviewees: list[Reviewee]
    pair_context_lookup: dict[tuple[int, int], Relationship]
    materialized: cache.MaterializedRows
    override_exclude_self_reviews: bool | None = None

    def stamp(self) -> str:
        return cache.reconcile_stamp(
            review_session=self.review_session,
            instrument=self.instrument,
            session_rule_set=self.session_rule_set,
            reviewers=self.reviewers,
            reviewees=self.reviewees,
            pair_context_lookup=self.pair_context_lookup,
            materialized=self.materialized,
            override_exclude_self_reviews=self.override_exclude_self_reviews,
        )


Undo = Callable[[], None]


def _set(obj: Any, attr: str, value: Any) -> Undo:
    """Assign, and hand back the restore."""
    original = getattr(obj, attr)

    def undo() -> None:
        setattr(obj, attr, original)

    assert original != value, f"{attr} was already {value!r}"
    setattr(obj, attr, value)
    return undo


def _flip(obj: Any, attr: str) -> Undo:
    """``_set`` to the opposite of whatever the flag currently is.

    Written after a case asserted ``self_reviews_active = True`` on a
    session that defaults to ``True``: the mutation was a no-op, and
    "the stamp did not move" was the correct answer to a question the
    test had not actually asked.
    """
    return _set(obj, attr, not getattr(obj, attr))


@pytest.fixture
def inputs(db: Session) -> Inputs:
    user = User(email="op-stamp@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code="stamp-1", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()

    reviewers = [
        Reviewer(
            session_id=review_session.id,
            name="Alice",
            email="alice@example.edu",
            tag_1="Team A",
        ),
        Reviewer(
            session_id=review_session.id,
            name="Bob",
            email="bob@example.edu",
            tag_1="Team B",
        ),
    ]
    reviewees = [
        Reviewee(
            session_id=review_session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
            tag_1="Team A",
        ),
        Reviewee(
            session_id=review_session.id,
            name="Dan",
            email_or_identifier="dan@example.edu",
            tag_1="Team B",
        ),
    ]
    db.add_all([*reviewers, *reviewees])
    db.flush()

    relationship = Relationship(
        session_id=review_session.id,
        reviewer_id=reviewers[0].id,
        reviewee_id=reviewees[0].id,
        tag_1="mentor",
    )
    db.add(relationship)
    db.flush()

    instrument = ensure_default_instrument(db, review_session)
    rule_set = SessionRuleSet(
        session_id=review_session.id,
        name="Full Matrix",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(rule_set)
    db.flush()
    instrument.rule_set_id = rule_set.id
    db.flush()

    return Inputs(
        review_session=review_session,
        instrument=instrument,
        session_rule_set=rule_set,
        reviewers=list(reviewers),
        reviewees=list(reviewees),
        pair_context_lookup={
            (relationship.reviewer_id, relationship.reviewee_id): relationship
        },
        materialized=cache.MaterializedRows(count=4, max_id=40),
    )


# --- the equality half -----------------------------------------------


def test_same_inputs_give_the_same_stamp(inputs: Inputs) -> None:
    assert inputs.stamp() == inputs.stamp()


def test_the_stamp_carries_its_version_and_fits_the_column(
    inputs: Inputs,
) -> None:
    stamp = inputs.stamp()
    assert stamp.startswith(f"{cache.STAMP_VERSION}:")
    # 3 + 64. The column is String(80); a stamp that outgrew it would
    # be truncated on Postgres and collide with its own neighbours.
    assert len(stamp) == 67
    assert len(stamp) <= 80


def test_roster_order_does_not_move_the_stamp(inputs: Inputs) -> None:
    """The caller's query order is not part of the answer, so it must
    not be part of the stamp — otherwise a changed ``ORDER BY``
    anywhere upstream invalidates every cached verdict at once."""
    before = inputs.stamp()
    inputs.reviewers = list(reversed(inputs.reviewers))
    inputs.reviewees = list(reversed(inputs.reviewees))
    assert inputs.stamp() == before


def test_an_unread_roster_column_does_not_move_the_stamp(
    inputs: Inputs,
) -> None:
    """``name`` is not addressable by any predicate, so it is not in
    the stamp. This is the negative case for the derivation test
    below: without it, a stamp over every column would pass that one
    while over-invalidating on every rename."""
    before = inputs.stamp()
    undo = _set(inputs.reviewers[0], "name", "Alice Renamed")
    assert inputs.stamp() == before
    undo()


# --- the half that matters -------------------------------------------


def _roster_cases() -> list[tuple[str, Callable[[Inputs], Undo]]]:
    return [
        (
            "reviewer email",
            lambda i: _set(i.reviewers[0], "email", "moved@example.edu"),
        ),
        ("reviewer tag_1", lambda i: _set(i.reviewers[0], "tag_1", "Team Z")),
        ("reviewer tag_2", lambda i: _set(i.reviewers[0], "tag_2", "x")),
        ("reviewer tag_3", lambda i: _set(i.reviewers[0], "tag_3", "x")),
        ("reviewer status", lambda i: _set(i.reviewers[0], "status", "removed")),
        (
            "reviewee identifier",
            lambda i: _set(
                i.reviewees[0], "email_or_identifier", "moved@example.edu"
            ),
        ),
        ("reviewee tag_1", lambda i: _set(i.reviewees[0], "tag_1", "Team Z")),
        ("reviewee status", lambda i: _set(i.reviewees[0], "status", "removed")),
    ]


def _shape_cases() -> list[tuple[str, Callable[[Inputs], Undo]]]:
    def drop_reviewer(i: Inputs) -> Undo:
        original = list(i.reviewers)
        i.reviewers = original[:1]
        return lambda: setattr(i, "reviewers", original)

    def add_reviewee(i: Inputs) -> Undo:
        original = list(i.reviewees)
        extra = Reviewee(
            session_id=i.review_session.id,
            name="Erin",
            email_or_identifier="erin@example.edu",
        )
        extra.id = max(r.id for r in original) + 1
        i.reviewees = [*original, extra]
        return lambda: setattr(i, "reviewees", original)

    def drop_relationship(i: Inputs) -> Undo:
        original = dict(i.pair_context_lookup)
        i.pair_context_lookup = {}
        return lambda: setattr(i, "pair_context_lookup", original)

    return [
        ("a reviewer leaves the roster", drop_reviewer),
        ("a reviewee joins the roster", add_reviewee),
        ("the relationships table empties", drop_relationship),
    ]


def _relationship_cases() -> list[tuple[str, Callable[[Inputs], Undo]]]:
    def row(i: Inputs) -> Relationship:
        return next(iter(i.pair_context_lookup.values()))

    return [
        ("pair_context tag_1", lambda i: _set(row(i), "tag_1", "peer")),
        ("pair_context tag_2", lambda i: _set(row(i), "tag_2", "x")),
        # Not over-coverage: ``fields.get_field_value`` skips a
        # non-active row, so every pair_context predicate reads None
        # against it and the fan-out can move.
        ("pair_context status", lambda i: _set(row(i), "status", "inactive")),
    ]


def _rule_cases() -> list[tuple[str, Callable[[Inputs], Undo]]]:
    return [
        (
            "the rule's predicates",
            lambda i: _set(
                i.session_rule_set,
                "rules_json",
                [{"field": "reviewer.tag1", "op": "eq", "value": "Team A"}],
            ),
        ),
        (
            "the rule's combinator",
            lambda i: _set(i.session_rule_set, "combinator", "ANY_OF"),
        ),
        (
            "the rule's exclude_self_reviews",
            lambda i: _flip(i.session_rule_set, "exclude_self_reviews"),
        ),
        (
            "the rule's name",
            lambda i: _set(i.session_rule_set, "name", "Renamed"),
        ),
        # Codex P1 on #2519. ``seed`` reaches the engine inside
        # ``_session_rule_set_to_schema``'s ``options=`` block, not as
        # a named argument, and becomes the ``fallback_seed`` for a
        # RANDOM-strategy quota with no seed of its own: change it and
        # a different set of pairs survives with nothing else moving.
        (
            "the rule's selection seed",
            lambda i: _set(i.session_rule_set, "seed", 7),
        ),
        (
            "which rule is pinned",
            lambda i: _set(i.instrument, "rule_set_id", 9999),
        ),
        (
            "the instrument is unpinned",
            lambda i: _set(i, "session_rule_set", None),
        ),
        (
            "the instrument's group_kind",
            lambda i: _set(i.instrument, "group_kind", "reviewee.tag1"),
        ),
        (
            "the session's self-review toggle",
            lambda i: _flip(i.review_session, "self_reviews_active"),
        ),
        (
            "the caller's self-review override",
            lambda i: _set(i, "override_exclude_self_reviews", True),
        ),
    ]


def _row_set_cases() -> list[tuple[str, Callable[[Inputs], Undo]]]:
    return [
        (
            "a row is deleted",
            lambda i: _set(
                i, "materialized", cache.MaterializedRows(count=3, max_id=40)
            ),
        ),
        (
            "a row is inserted",
            lambda i: _set(
                i, "materialized", cache.MaterializedRows(count=5, max_id=41)
            ),
        ),
        (
            "one out, one in — the count returns but the id does not",
            lambda i: _set(
                i, "materialized", cache.MaterializedRows(count=4, max_id=41)
            ),
        ),
        (
            "the instrument has never generated",
            lambda i: _set(
                i, "materialized", cache.MaterializedRows(count=0, max_id=None)
            ),
        ),
    ]


ALL_CASES = [
    *_roster_cases(),
    *_shape_cases(),
    *_relationship_cases(),
    *_rule_cases(),
    *_row_set_cases(),
]


@pytest.mark.parametrize(
    "mutate", [c[1] for c in ALL_CASES], ids=[c[0] for c in ALL_CASES]
)
def test_every_input_moves_the_stamp(
    inputs: Inputs, mutate: Callable[[Inputs], Undo]
) -> None:
    before = inputs.stamp()
    undo = mutate(inputs)
    assert inputs.stamp() != before
    undo()
    # The restore is asserted so a case cannot leave the fixture
    # changed — and so "different" above cannot be an artefact of an
    # earlier case that did.
    assert inputs.stamp() == before


def test_an_empty_tag_is_not_an_absent_one(inputs: Inputs) -> None:
    """``None`` and ``""`` are different to a predicate, so they are
    different to the stamp. A serialisation that coerced either way
    would merge two rosters that generate differently."""
    assert inputs.reviewers[0].tag_2 is None
    as_none = inputs.stamp()
    undo = _set(inputs.reviewers[0], "tag_2", "")
    as_empty = inputs.stamp()
    undo()
    assert as_none != as_empty
    assert inputs.stamp() == as_none


def test_a_rule_reordered_but_not_changed_keeps_its_stamp(
    inputs: Inputs,
) -> None:
    """``rules_json`` is a JSON column, so two loads of the same rule
    can hand back dicts whose keys are in different orders. Without a
    canonical serialisation that reads as a different rule and every
    cached verdict in the session misses.

    This is the only thing ``sort_keys=True`` buys: the payload's own
    keys are written in a fixed order at the call site. Added because
    a mutation that turned the flag off left every other case in this
    file passing.
    """
    rule = {"field": "reviewer.tag1", "op": "eq", "value": "Team A"}
    reordered = {"value": "Team A", "op": "eq", "field": "reviewer.tag1"}
    assert list(rule) != list(reordered)

    undo = _set(inputs.session_rule_set, "rules_json", [rule])
    one_way = inputs.stamp()
    undo()
    undo = _set(inputs.session_rule_set, "rules_json", [reordered])
    other_way = inputs.stamp()
    undo()
    assert one_way == other_way


def test_the_roster_columns_come_from_FIELD_MAP(
    inputs: Inputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``FIELD_MAP``'s docstring promises that adding an addressable
    field is "a one-row edit here and nowhere else". If the stamp kept
    its own copy of the column list that promise would be false, and
    the failure would be silent: a predicate on the new field would
    move the fan-out while the stamp stayed equal.

    Paired with ``test_an_unread_roster_column_does_not_move_the_stamp``
    above, which shows ``name`` is outside the stamp until the one-row
    edit brings it in.
    """
    monkeypatch.setitem(FIELD_MAP, "reviewer.name", ("reviewer", "name"))
    before = inputs.stamp()
    undo = _set(inputs.reviewers[0], "name", "Alice Renamed")
    assert inputs.stamp() != before
    undo()


def test_every_rule_set_column_is_decided_about(inputs: Inputs) -> None:
    """A new column on ``SessionRuleSet`` has to be either in the
    digest or named here as deliberately out.

    Written after the seed was missed (Codex P1 on #2519): it reaches
    the engine inside ``_session_rule_set_to_schema``'s ``options=``
    block rather than as a named argument, so reading the constructor's
    arguments — which is how the field list was built — skipped it. A
    column list is something the code can be asked for; a reading is
    not, and it was the reading that was wrong.
    """
    #: Columns deliberately outside the digest, each with the reason
    #: it cannot change which pairs the engine produces.
    NOT_IN_THE_DIGEST = {
        # The rule is reached through ``instrument.rule_set_id``, which
        # the stamp already carries, and a rule row does not move
        # between sessions.
        "session_id",
        # Bookkeeping, and no reader in the generate path. ``updated_at``
        # would in fact be a safe over-cover — it moves on any write —
        # but hashing it would invalidate on a no-op Save, which is the
        # cache's most common hit and the reason the plan's judgment
        # calls settled on hashing content rather than a timestamp.
        "created_at",
        "updated_at",
    }
    columns = {c.key for c in SessionRuleSet.__table__.columns}
    digested = set(cache._rule_set_digest(inputs.session_rule_set))
    # ``rules_json`` is digested under the shorter key the engine's own
    # schema uses.
    digested = {"rules_json" if k == "rules" else k for k in digested}
    assert columns - digested == NOT_IN_THE_DIGEST, (
        "a SessionRuleSet column is neither digested nor excluded: "
        f"{sorted(columns - digested - NOT_IN_THE_DIGEST)}"
    )


# --- the materialized-row query --------------------------------------


def test_materialized_rows_counts_per_instrument_within_the_session(
    db: Session, inputs: Inputs
) -> None:
    """Grouped by instrument, scoped to the session.

    The decoy is load-bearing: with one session in the fixture, a
    helper that forgot its ``session_id`` filter would pass — which is
    exactly how three mutants survived 19R Item 1's first test pass.
    """
    other_user = User(email="op-stamp-decoy@example.edu")
    db.add(other_user)
    db.flush()
    decoy_session = ReviewSession(
        name="Other", code="stamp-decoy", created_by_user_id=other_user.id
    )
    db.add(decoy_session)
    db.flush()
    decoy_reviewer = Reviewer(
        session_id=decoy_session.id, name="Zoe", email="zoe@example.edu"
    )
    decoy_reviewees = [
        Reviewee(
            session_id=decoy_session.id,
            name=f"Yves {n}",
            email_or_identifier=f"yves{n}@example.edu",
        )
        for n in range(3)
    ]
    db.add_all([decoy_reviewer, *decoy_reviewees])
    db.flush()
    decoy_instrument = ensure_default_instrument(db, decoy_session)
    # Distinct pairs: ``uq_assignment_unique`` is on
    # ``(session, reviewer, reviewee, instrument)``.
    db.add_all(
        Assignment(
            session_id=decoy_session.id,
            instrument_id=decoy_instrument.id,
            reviewer_id=decoy_reviewer.id,
            reviewee_id=decoy_reviewee.id,
        )
        for decoy_reviewee in decoy_reviewees
    )

    rows = [
        Assignment(
            session_id=inputs.review_session.id,
            instrument_id=inputs.instrument.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
        for reviewer in inputs.reviewers
        for reviewee in inputs.reviewees
    ]
    db.add_all(rows)
    db.flush()

    by_instrument = cache.materialized_rows_by_instrument(
        db, inputs.review_session.id
    )
    assert set(by_instrument) == {inputs.instrument.id}
    summary = by_instrument[inputs.instrument.id]
    assert summary.count == 4
    assert summary.max_id == max(row.id for row in rows)


def test_an_instrument_with_no_rows_reads_as_empty(
    db: Session, inputs: Inputs
) -> None:
    by_instrument = cache.materialized_rows_by_instrument(
        db, inputs.review_session.id
    )
    assert inputs.instrument.id not in by_instrument
    assert cache.rows_for(by_instrument, inputs.instrument.id) == (
        cache.MaterializedRows(count=0, max_id=None)
    )
