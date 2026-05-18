"""Unit tests for ``app/services/rules/engine.py`` — Segment 13A
PR 2.

Covers the end-to-end ``evaluate(...)`` algorithm: candidate
construction, self-review desugar, content rules under each
combinator, composite recursion, quota application, and determinism
across repeated runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.rules import (
    Combinator,
    CompositeOp,
    CompositeRule,
    FilterRule,
    MatchRule,
    Predicate,
    QuotaRule,
    QuotaScope,
    QuotaSelection,
    RuleSetOptions,
    RuleSetSchema,
    SelectionStrategy,
)
from app.services.rules.engine import evaluate, validate_rule_set


@dataclass
class Reviewer:
    email: str
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None


@dataclass
class Reviewee:
    email_or_identifier: str
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None


def _build_population(
    *, groups: int, per_group: int, with_lead: bool = False
) -> tuple[list[Reviewer], list[Reviewee]]:
    """Build a small symmetric population.

    Each member has ``tag_1`` set to ``Group{NN}`` and ``tag_2`` set to
    ``Lead`` for the first member of each group when ``with_lead`` is
    true; otherwise ``Member``.
    """

    reviewers: list[Reviewer] = []
    reviewees: list[Reviewee] = []
    for g in range(groups):
        for m in range(per_group):
            email = f"g{g:02d}m{m:02d}@x.edu"
            tag1 = f"Group{g:02d}"
            tag2 = "Lead" if (with_lead and m == 0) else "Member"
            reviewers.append(Reviewer(email=email, tag_1=tag1, tag_2=tag2))
            reviewees.append(
                Reviewee(
                    email_or_identifier=email, tag_1=tag1, tag_2=tag2
                )
            )
    return reviewers, reviewees


def _ruleset(
    *,
    combinator: Combinator = Combinator.ALL_OF,
    rules: list = (),
    exclude_self: bool = True,
    seed: int | None = None,
) -> RuleSetSchema:
    return RuleSetSchema(
        name="test",
        combinator=combinator,
        rules=list(rules),
        options=RuleSetOptions(excludeSelfReviews=exclude_self, seed=seed),
    )


# ---------------------------------------------------------------------------
# Self-review desugar + override
# ---------------------------------------------------------------------------


def test_exclude_self_reviews_drops_same_email_pairs() -> None:
    reviewers, reviewees = _build_population(groups=2, per_group=2)
    result = evaluate(
        _ruleset(),
        reviewers=reviewers,
        reviewees=reviewees,
    )
    for reviewer, reviewee in result.pairs:
        assert reviewer.email != reviewee.email_or_identifier
    assert result.excluded_counts.get("self_review") == 4


def test_override_exclude_self_reviews_shadows_ruleset_default() -> None:
    reviewers, reviewees = _build_population(groups=1, per_group=3)
    rule_set = _ruleset(exclude_self=True)
    overridden = evaluate(
        rule_set,
        reviewers=reviewers,
        reviewees=reviewees,
        override_exclude_self_reviews=False,
    )
    # 3×3 = 9 pairs preserved including self-reviews.
    assert len(overridden.pairs) == 9
    assert "self_review" not in overridden.excluded_counts
    # Default (no override) still strips self-reviews.
    default = evaluate(rule_set, reviewers=reviewers, reviewees=reviewees)
    assert len(default.pairs) == 6


# ---------------------------------------------------------------------------
# Combinators
# ---------------------------------------------------------------------------


def test_all_of_intersects_per_rule_allowed_sets() -> None:
    """Intra-group AND lead-only ⇒ pairs that are both intra-group
    and (reviewer is Lead AND reviewee is Lead)."""

    reviewers, reviewees = _build_population(
        groups=2, per_group=3, with_lead=True
    )
    result = evaluate(
        _ruleset(
            combinator=Combinator.ALL_OF,
            rules=[
                MatchRule(
                    id="intra",
                    predicate=Predicate(
                        field="reviewer.tag1",
                        operator="same_as",
                        operand="reviewee.tag1",
                    ),
                ),
                MatchRule(
                    id="rev_lead",
                    predicate=Predicate(
                        field="reviewer.tag2",
                        operator="equals",
                        operand="Lead",
                    ),
                ),
                MatchRule(
                    id="rvw_lead",
                    predicate=Predicate(
                        field="reviewee.tag2",
                        operator="equals",
                        operand="Lead",
                    ),
                ),
            ],
        ),
        reviewers=reviewers,
        reviewees=reviewees,
    )
    # Self-review is excluded by default, so the only intra-group
    # Lead↔Lead pair within a group is the lead with herself, which
    # gets dropped. Thus zero pairs.
    assert result.pairs == []


def test_any_of_unions_per_rule_allowed_sets() -> None:
    """Intra-group OR same-tag2: pairs that match either rule survive."""

    reviewers = [
        Reviewer(email="a@x.edu", tag_1="A", tag_2="X"),
        Reviewer(email="b@x.edu", tag_1="B", tag_2="X"),
    ]
    reviewees = [
        Reviewee(email_or_identifier="c@x.edu", tag_1="A", tag_2="Y"),
        Reviewee(email_or_identifier="d@x.edu", tag_1="C", tag_2="X"),
    ]
    rs = _ruleset(
        combinator=Combinator.ANY_OF,
        rules=[
            MatchRule(
                id="intra",
                predicate=Predicate(
                    field="reviewer.tag1",
                    operator="same_as",
                    operand="reviewee.tag1",
                ),
            ),
            MatchRule(
                id="same_tag2",
                predicate=Predicate(
                    field="reviewer.tag2",
                    operator="same_as",
                    operand="reviewee.tag2",
                ),
            ),
        ],
        exclude_self=False,
    )
    result = evaluate(rs, reviewers=reviewers, reviewees=reviewees)
    pair_keys = {
        (r.email, e.email_or_identifier) for r, e in result.pairs
    }
    # (a, c) intra; (a, d) same tag2; (b, d) same tag2.
    assert pair_keys == {
        ("a@x.edu", "c@x.edu"),
        ("a@x.edu", "d@x.edu"),
        ("b@x.edu", "d@x.edu"),
    }


def test_any_of_keeps_distinct_reviewers_sharing_an_email() -> None:
    """Two distinct reviewers with the same email address must not
    collapse into one pair — the engine dedups by object identity,
    not by email (which can legitimately collide for non-CSV-added
    roster rows)."""

    twin_a = Reviewer(email="twin@x.edu", tag_1="A", tag_2="X")
    twin_b = Reviewer(email="twin@x.edu", tag_1="A", tag_2="X")
    reviewers = [twin_a, twin_b]
    reviewees = [Reviewee(email_or_identifier="c@x.edu", tag_1="A", tag_2="X")]
    rs = _ruleset(
        combinator=Combinator.ANY_OF,
        rules=[
            MatchRule(
                id="intra",
                predicate=Predicate(
                    field="reviewer.tag1",
                    operator="same_as",
                    operand="reviewee.tag1",
                ),
            ),
        ],
        exclude_self=False,
    )
    result = evaluate(rs, reviewers=reviewers, reviewees=reviewees)
    # Both twins → c. An email-keyed dedup would merge them to one.
    assert len(result.pairs) == 2
    assert {id(r) for r, _ in result.pairs} == {id(twin_a), id(twin_b)}


def test_pipeline_applies_rules_in_declaration_order() -> None:
    """Start with everything, MATCH intra-group, then FILTER away
    leads. Final = intra-group non-lead pairs (excl. self)."""

    reviewers, reviewees = _build_population(
        groups=2, per_group=3, with_lead=True
    )
    rs = _ruleset(
        combinator=Combinator.PIPELINE,
        rules=[
            MatchRule(
                id="intra",
                predicate=Predicate(
                    field="reviewer.tag1",
                    operator="same_as",
                    operand="reviewee.tag1",
                ),
            ),
            FilterRule(
                id="strip_leads",
                predicate=Predicate(
                    field="reviewer.tag2", operator="equals", operand="Lead"
                ),
            ),
        ],
    )
    result = evaluate(rs, reviewers=reviewers, reviewees=reviewees)
    for r, _ in result.pairs:
        assert r.tag_2 == "Member"


# ---------------------------------------------------------------------------
# Composite recursion
# ---------------------------------------------------------------------------


def test_composite_and_or_nest_correctly() -> None:
    """Composite AND of two MATCH children inside an outer ALL_OF
    behaves the same as listing the children directly under ALL_OF."""

    reviewers = [
        Reviewer(email="a@x.edu", tag_1="A", tag_2="L"),
        Reviewer(email="b@x.edu", tag_1="A", tag_2="M"),
    ]
    reviewees = [
        Reviewee(email_or_identifier="c@x.edu", tag_1="A", tag_2="L"),
        Reviewee(email_or_identifier="d@x.edu", tag_1="B", tag_2="L"),
    ]
    composite = CompositeRule(
        id="leads_intra",
        op=CompositeOp.AND,
        rules=[
            MatchRule(
                id="lead_r",
                predicate=Predicate(
                    field="reviewer.tag2", operator="equals", operand="L"
                ),
            ),
            MatchRule(
                id="intra",
                predicate=Predicate(
                    field="reviewer.tag1",
                    operator="same_as",
                    operand="reviewee.tag1",
                ),
            ),
        ],
    )
    result = evaluate(
        _ruleset(
            combinator=Combinator.ALL_OF,
            rules=[composite],
            exclude_self=False,
        ),
        reviewers=reviewers,
        reviewees=reviewees,
    )
    assert {(r.email, e.email_or_identifier) for r, e in result.pairs} == {
        ("a@x.edu", "c@x.edu"),
    }


# ---------------------------------------------------------------------------
# Quotas
# ---------------------------------------------------------------------------


def test_quota_caps_per_reviewee_at_max() -> None:
    reviewers, reviewees = _build_population(groups=1, per_group=6)
    quota = QuotaRule(
        id="three_each",
        scope=QuotaScope.PER_REVIEWEE,
        min=3,
        max=3,
        selection=QuotaSelection(strategy=SelectionStrategy.RANDOM, seed=1),
    )
    result = evaluate(
        _ruleset(rules=[quota]),
        reviewers=reviewers,
        reviewees=reviewees,
    )
    by_reviewee: dict[str, int] = {}
    for _, e in result.pairs:
        by_reviewee[e.email_or_identifier] = (
            by_reviewee.get(e.email_or_identifier, 0) + 1
        )
    assert all(count == 3 for count in by_reviewee.values())
    assert result.excluded_counts.get("quota.per_reviewee", 0) > 0


def test_quota_under_min_populates_warnings() -> None:
    reviewers, reviewees = _build_population(groups=1, per_group=2)
    quota = QuotaRule(
        id="three_each",
        scope=QuotaScope.PER_REVIEWEE,
        min=3,
        max=3,
        selection=QuotaSelection(strategy=SelectionStrategy.ROUND_ROBIN),
    )
    result = evaluate(
        _ruleset(rules=[quota]),
        reviewers=reviewers,
        reviewees=reviewees,
    )
    assert any("minimum 3 not met" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_repeated_runs_with_same_seed_produce_identical_pairs() -> None:
    reviewers, reviewees = _build_population(groups=4, per_group=5)
    quota = QuotaRule(
        id="q",
        scope=QuotaScope.PER_REVIEWEE,
        min=None,
        max=3,
        selection=QuotaSelection(strategy=SelectionStrategy.RANDOM, seed=42),
    )
    rs = _ruleset(rules=[quota])
    runs = [
        evaluate(rs, reviewers=reviewers, reviewees=reviewees).pairs
        for _ in range(100)
    ]
    first = [
        (r.email, e.email_or_identifier) for r, e in runs[0]
    ]
    for run in runs[1:]:
        assert [
            (r.email, e.email_or_identifier) for r, e in run
        ] == first


def test_deterministic_pair_emit_order_is_lex_email() -> None:
    reviewers, reviewees = _build_population(groups=2, per_group=2)
    result = evaluate(
        _ruleset(),
        reviewers=reviewers,
        reviewees=reviewees,
    )
    keys = [(r.email, e.email_or_identifier) for r, e in result.pairs]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Empty populations
# ---------------------------------------------------------------------------


def test_empty_reviewers_yields_no_pairs_and_warning() -> None:
    result = evaluate(
        _ruleset(),
        reviewers=[],
        reviewees=[Reviewee(email_or_identifier="b@x.edu")],
    )
    assert result.pairs == []
    assert any("zero" in w for w in result.warnings)


def test_empty_reviewees_yields_no_pairs() -> None:
    result = evaluate(
        _ruleset(),
        reviewers=[Reviewer(email="a@x.edu")],
        reviewees=[],
    )
    assert result.pairs == []


def test_both_empty_yields_no_pairs() -> None:
    result = evaluate(_ruleset(), reviewers=[], reviewees=[])
    assert result.pairs == []


# ---------------------------------------------------------------------------
# validate_rule_set
# ---------------------------------------------------------------------------


def test_validate_flags_unconstrained_full_matrix_when_self_review_allowed() -> None:
    rs = _ruleset(rules=[], exclude_self=False)
    issues = validate_rule_set(rs)
    assert any("no rules" in issue.message for issue in issues)


def test_validate_flags_quota_min_exceeding_population() -> None:
    quota = QuotaRule(
        id="impossible",
        scope=QuotaScope.PER_REVIEWEE,
        min=10,
        max=10,
        selection=QuotaSelection(strategy=SelectionStrategy.ROUND_ROBIN),
    )
    rs = _ruleset(rules=[quota])
    issues = validate_rule_set(
        rs,
        reviewers=[Reviewer(email="a@x.edu")],
        reviewees=[Reviewee(email_or_identifier="b@x.edu")],
    )
    assert any(
        "exceeds PER_REVIEWEE population size" in issue.message
        for issue in issues
    )


def test_validate_flags_empty_populations() -> None:
    rs = _ruleset()
    issues = validate_rule_set(rs, reviewers=[], reviewees=[])
    messages = {issue.message for issue in issues}
    assert "reviewer population is empty" in messages
    assert "reviewee population is empty" in messages
