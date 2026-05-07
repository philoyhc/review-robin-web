"""Unit tests for ``app/services/rules/quotas.py`` — Segment 13A
PR 2."""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.rules import (
    QuotaRule,
    QuotaScope,
    QuotaSelection,
    SelectionStrategy,
)
from app.services.rules.quotas import apply_quota


@dataclass
class Reviewer:
    email: str


@dataclass
class Reviewee:
    email_or_identifier: str


def _quota(
    *,
    rule_id: str = "q",
    scope: QuotaScope,
    min_: int | None,
    max_: int | None,
    strategy: SelectionStrategy,
    seed: int | None = None,
) -> QuotaRule:
    return QuotaRule(
        id=rule_id,
        scope=scope,
        min=min_,
        max=max_,
        selection=QuotaSelection(strategy=strategy, seed=seed),
    )


def _build_pairs(
    *, n_reviewers: int, n_reviewees: int
) -> list[tuple[Reviewer, Reviewee]]:
    reviewers = [
        Reviewer(email=f"r{i:02d}@x.edu") for i in range(n_reviewers)
    ]
    reviewees = [
        Reviewee(email_or_identifier=f"e{i:02d}@x.edu")
        for i in range(n_reviewees)
    ]
    return [(r, e) for r in reviewers for e in reviewees]


def test_round_robin_caps_at_max_per_reviewee() -> None:
    pairs = _build_pairs(n_reviewers=5, n_reviewees=2)
    rule = _quota(
        scope=QuotaScope.PER_REVIEWEE,
        min_=None,
        max_=3,
        strategy=SelectionStrategy.ROUND_ROBIN,
    )
    survivors, excluded, warnings = apply_quota(
        pairs, rule, fallback_seed=0
    )
    assert len(survivors) == 6  # 3 per reviewee × 2 reviewees
    assert excluded == 4
    assert warnings == []


def test_random_caps_at_max_and_is_seeded_deterministic() -> None:
    pairs = _build_pairs(n_reviewers=10, n_reviewees=2)
    rule = _quota(
        scope=QuotaScope.PER_REVIEWEE,
        min_=None,
        max_=3,
        strategy=SelectionStrategy.RANDOM,
        seed=42,
    )
    runs = [apply_quota(pairs, rule, fallback_seed=0)[0] for _ in range(10)]
    first = runs[0]
    for run in runs[1:]:
        assert run == first
    assert len(first) == 6


def test_random_with_different_seeds_yields_different_pairs() -> None:
    pairs = _build_pairs(n_reviewers=20, n_reviewees=1)
    seen: set[tuple[str, ...]] = set()
    for seed in range(10):
        rule = _quota(
            scope=QuotaScope.PER_REVIEWEE,
            min_=None,
            max_=5,
            strategy=SelectionStrategy.RANDOM,
            seed=seed,
        )
        survivors, _, _ = apply_quota(pairs, rule, fallback_seed=0)
        seen.add(tuple(r.email for r, _ in survivors))
    assert len(seen) > 1


def test_under_min_emits_warning_but_keeps_pairs() -> None:
    pairs = _build_pairs(n_reviewers=2, n_reviewees=1)
    rule = _quota(
        rule_id="three_each",
        scope=QuotaScope.PER_REVIEWEE,
        min_=3,
        max_=3,
        strategy=SelectionStrategy.ROUND_ROBIN,
    )
    survivors, excluded, warnings = apply_quota(
        pairs, rule, fallback_seed=0
    )
    assert len(survivors) == 2  # Only 2 candidates available.
    assert excluded == 0
    assert any("minimum 3 not met" in w for w in warnings)


def test_fallback_seed_used_when_rule_seed_is_none() -> None:
    """If a RANDOM quota carries no ``selection.seed``, the engine
    seeds it from the RuleSet ``options.seed`` (or revision id) the
    caller passes through ``fallback_seed``."""

    pairs = _build_pairs(n_reviewers=5, n_reviewees=1)
    rule = _quota(
        scope=QuotaScope.PER_REVIEWEE,
        min_=None,
        max_=2,
        strategy=SelectionStrategy.RANDOM,
        seed=None,
    )
    a = apply_quota(pairs, rule, fallback_seed=99)[0]
    b = apply_quota(pairs, rule, fallback_seed=99)[0]
    c = apply_quota(pairs, rule, fallback_seed=100)[0]
    assert a == b
    assert a != c


def test_per_reviewer_axis_groups_by_reviewer_email() -> None:
    pairs = _build_pairs(n_reviewers=2, n_reviewees=5)
    rule = _quota(
        scope=QuotaScope.PER_REVIEWER,
        min_=None,
        max_=2,
        strategy=SelectionStrategy.ROUND_ROBIN,
    )
    survivors, _, _ = apply_quota(pairs, rule, fallback_seed=0)
    by_reviewer: dict[str, int] = {}
    for r, _ in survivors:
        by_reviewer[r.email] = by_reviewer.get(r.email, 0) + 1
    assert all(count == 2 for count in by_reviewer.values())
    assert len(by_reviewer) == 2
