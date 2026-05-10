"""Unit coverage for Segment 15D PR 4 — engine consumption of
``pair_context.tag_N`` via the eager ``pair_context_lookup`` dict.

The engine binds the lookup to a ``ContextVar`` for the duration of
``evaluate()``; ``get_field_value`` reads it when resolving any
``pair_context.*`` field. Inactive rows (``status != "active"``)
are skipped at lookup time — the pair stays in the candidate set,
but pair_context predicates evaluate as if no row exists for it.

These tests exercise the engine end-to-end without going through
HTTP — that's the integration test's job. We use lightweight stub
objects in place of ORM rows so the engine sees ``id``, ``email``,
and ``email_or_identifier`` attributes plus a ``status`` /
``tag_*`` shape on the relationship stub.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.rules import (
    Combinator,
    FilterRule,
    MatchRule,
    Predicate,
    RuleSetSchema,
)
from app.services.rules import engine
from app.services.rules.fields import (
    get_field_value,
    reset_pair_context_lookup,
    set_pair_context_lookup,
)


@dataclass
class _Reviewer:
    id: int
    email: str
    tag_1: str | None = None


@dataclass
class _Reviewee:
    id: int
    email_or_identifier: str
    tag_1: str | None = None


@dataclass
class _Relationship:
    reviewer_id: int
    reviewee_id: int
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None
    status: str = "active"


def _ruleset(*rules: object, combinator: Combinator = Combinator.ALL_OF) -> RuleSetSchema:
    return RuleSetSchema(
        name="t",
        description="",
        combinator=combinator,
        rules=list(rules),  # type: ignore[arg-type]
    )


def test_get_field_value_reads_active_relationship_tag() -> None:
    reviewer = _Reviewer(id=1, email="a@example.edu")
    reviewee = _Reviewee(id=10, email_or_identifier="b@example.edu")
    rel = _Relationship(
        reviewer_id=1, reviewee_id=10, tag_1="Mentor", status="active"
    )
    token = set_pair_context_lookup({(1, 10): rel})  # type: ignore[arg-type]
    try:
        value = get_field_value(
            "pair_context.tag1", reviewer=reviewer, reviewee=reviewee
        )
    finally:
        reset_pair_context_lookup(token)
    assert value == "Mentor"


def test_get_field_value_returns_none_for_inactive_relationship() -> None:
    """Skip-at-lookup: status='inactive' rows are invisible to
    pair_context predicates. The pair itself is still a candidate."""

    reviewer = _Reviewer(id=1, email="a@example.edu")
    reviewee = _Reviewee(id=10, email_or_identifier="b@example.edu")
    rel = _Relationship(
        reviewer_id=1, reviewee_id=10, tag_1="Mentor", status="inactive"
    )
    token = set_pair_context_lookup({(1, 10): rel})  # type: ignore[arg-type]
    try:
        value = get_field_value(
            "pair_context.tag1", reviewer=reviewer, reviewee=reviewee
        )
    finally:
        reset_pair_context_lookup(token)
    assert value is None


def test_get_field_value_returns_none_when_no_lookup_bound() -> None:
    """Without ``set_pair_context_lookup``, pair_context fields
    resolve to None — same behaviour the PR 3 stub had."""

    reviewer = _Reviewer(id=1, email="a@example.edu")
    reviewee = _Reviewee(id=10, email_or_identifier="b@example.edu")
    value = get_field_value(
        "pair_context.tag1", reviewer=reviewer, reviewee=reviewee
    )
    assert value is None


def test_get_field_value_returns_none_when_pair_missing_from_lookup() -> None:
    reviewer = _Reviewer(id=1, email="a@example.edu")
    reviewee = _Reviewee(id=10, email_or_identifier="b@example.edu")
    token = set_pair_context_lookup({})  # type: ignore[arg-type]
    try:
        value = get_field_value(
            "pair_context.tag1", reviewer=reviewer, reviewee=reviewee
        )
    finally:
        reset_pair_context_lookup(token)
    assert value is None


def test_evaluate_with_pair_context_match_rule() -> None:
    """A MATCH rule on ``pair_context.tag1 == 'Mentor'`` keeps only
    pairs whose relationships row carries that tag."""

    alice = _Reviewer(id=1, email="alice@example.edu")
    bob = _Reviewer(id=2, email="bob@example.edu")
    carol = _Reviewee(id=10, email_or_identifier="carol@example.edu")
    dan = _Reviewee(id=11, email_or_identifier="dan@example.edu")

    lookup = {
        (1, 10): _Relationship(reviewer_id=1, reviewee_id=10, tag_1="Mentor"),
        (2, 11): _Relationship(reviewer_id=2, reviewee_id=11, tag_1="COI"),
        # (1, 11) and (2, 10) have no relationship rows.
    }

    rs = _ruleset(
        MatchRule(
            id="r1",
            predicate=Predicate(
                field="pair_context.tag1",
                operator="equals",
                operand="Mentor",
            ),
        )
    )
    result = engine.evaluate(
        rs,
        reviewers=[alice, bob],
        reviewees=[carol, dan],
        override_exclude_self_reviews=False,
        pair_context_lookup=lookup,  # type: ignore[arg-type]
    )
    assert {(r.id, e.id) for r, e in result.pairs} == {(1, 10)}


def test_evaluate_with_pair_context_filter_rule() -> None:
    """A FILTER rule on ``pair_context.tag1 == 'COI'`` drops the
    matching pair and keeps the rest."""

    alice = _Reviewer(id=1, email="alice@example.edu")
    bob = _Reviewer(id=2, email="bob@example.edu")
    carol = _Reviewee(id=10, email_or_identifier="carol@example.edu")
    dan = _Reviewee(id=11, email_or_identifier="dan@example.edu")

    lookup = {
        (1, 10): _Relationship(reviewer_id=1, reviewee_id=10, tag_1="COI"),
    }

    rs = _ruleset(
        FilterRule(
            id="r1",
            predicate=Predicate(
                field="pair_context.tag1",
                operator="equals",
                operand="COI",
            ),
        )
    )
    result = engine.evaluate(
        rs,
        reviewers=[alice, bob],
        reviewees=[carol, dan],
        override_exclude_self_reviews=False,
        pair_context_lookup=lookup,  # type: ignore[arg-type]
    )
    pair_ids = {(r.id, e.id) for r, e in result.pairs}
    assert (1, 10) not in pair_ids
    assert pair_ids == {(1, 11), (2, 10), (2, 11)}


def test_evaluate_inactive_row_invisible_but_pair_remains() -> None:
    """An inactive relationships row hides its tag values from
    pair_context predicates. The pair itself stays in the candidate
    set; reviewer / reviewee tag rules still see it."""

    alice = _Reviewer(id=1, email="alice@example.edu", tag_1="A-team")
    carol = _Reviewee(
        id=10, email_or_identifier="carol@example.edu", tag_1="A-team"
    )

    lookup = {
        (1, 10): _Relationship(
            reviewer_id=1, reviewee_id=10, tag_1="Mentor", status="inactive"
        ),
    }

    # MATCH on pair_context.tag1 — the inactive row's value is hidden,
    # so the predicate evaluates False and the pair is excluded.
    rs_pc = _ruleset(
        MatchRule(
            id="r1",
            predicate=Predicate(
                field="pair_context.tag1",
                operator="equals",
                operand="Mentor",
            ),
        )
    )
    result = engine.evaluate(
        rs_pc,
        reviewers=[alice],
        reviewees=[carol],
        override_exclude_self_reviews=False,
        pair_context_lookup=lookup,  # type: ignore[arg-type]
    )
    assert result.pairs == []

    # MATCH on reviewer.tag1 — still sees the pair (the relationship
    # row's status doesn't gate non-pair_context fields).
    rs_rev = _ruleset(
        MatchRule(
            id="r1",
            predicate=Predicate(
                field="reviewer.tag1",
                operator="equals",
                operand="A-team",
            ),
        )
    )
    result = engine.evaluate(
        rs_rev,
        reviewers=[alice],
        reviewees=[carol],
        override_exclude_self_reviews=False,
        pair_context_lookup=lookup,  # type: ignore[arg-type]
    )
    assert {(r.id, e.id) for r, e in result.pairs} == {(1, 10)}


def test_evaluate_resets_context_var_after_run() -> None:
    """The ContextVar is reset cleanly after ``evaluate()`` returns
    so tests / nested callers don't see leakage."""

    alice = _Reviewer(id=1, email="alice@example.edu")
    carol = _Reviewee(id=10, email_or_identifier="carol@example.edu")
    lookup = {
        (1, 10): _Relationship(reviewer_id=1, reviewee_id=10, tag_1="Mentor"),
    }
    rs = _ruleset()
    engine.evaluate(
        rs,
        reviewers=[alice],
        reviewees=[carol],
        override_exclude_self_reviews=False,
        pair_context_lookup=lookup,  # type: ignore[arg-type]
    )
    # Outside the evaluate() call, no lookup is bound.
    value = get_field_value(
        "pair_context.tag1", reviewer=alice, reviewee=carol
    )
    assert value is None


def test_evaluate_resets_context_var_on_exception() -> None:
    """Even when ``evaluate()`` raises, the ContextVar is reset so
    follow-up calls aren't poisoned."""

    alice = _Reviewer(id=1, email="alice@example.edu")
    carol = _Reviewee(id=10, email_or_identifier="carol@example.edu")
    lookup = {
        (1, 10): _Relationship(reviewer_id=1, reviewee_id=10, tag_1="Mentor"),
    }

    class _BoomRuleSet:
        """Trip the engine inside the try block (after the lookup has
        been bound to the ContextVar)."""

        @property
        def options(self):
            raise RuntimeError("boom")

    try:
        engine.evaluate(
            _BoomRuleSet(),  # type: ignore[arg-type]
            reviewers=[alice],
            reviewees=[carol],
            pair_context_lookup=lookup,  # type: ignore[arg-type]
        )
    except RuntimeError:
        pass

    # ContextVar reset cleanly despite the exception.
    value = get_field_value(
        "pair_context.tag1", reviewer=alice, reviewee=carol
    )
    assert value is None


def test_same_as_across_pair_context_and_reviewer() -> None:
    """``reviewer.tag1 same_as pair_context.tag1`` matches when the
    reviewer's tag matches the relationship row's tag (different
    'sides' so the cross-side validator is satisfied)."""

    alice = _Reviewer(id=1, email="alice@example.edu", tag_1="A")
    bob = _Reviewer(id=2, email="bob@example.edu", tag_1="A")
    carol = _Reviewee(id=10, email_or_identifier="carol@example.edu")

    lookup = {
        (1, 10): _Relationship(reviewer_id=1, reviewee_id=10, tag_1="A"),
        (2, 10): _Relationship(reviewer_id=2, reviewee_id=10, tag_1="B"),
    }

    rs = _ruleset(
        MatchRule(
            id="r1",
            predicate=Predicate(
                field="reviewer.tag1",
                operator="same_as",
                operand="pair_context.tag1",
            ),
        )
    )
    result = engine.evaluate(
        rs,
        reviewers=[alice, bob],
        reviewees=[carol],
        override_exclude_self_reviews=False,
        pair_context_lookup=lookup,  # type: ignore[arg-type]
    )
    assert {(r.id, e.id) for r, e in result.pairs} == {(1, 10)}
