"""Unit tests for ``app/services/rules/seeds.py`` — Segment 13A
PR 3.

Each canonical seed is run through PR 2's engine on a fixture
population and the surviving pair count + a sample of pairs are
pinned. These tests are the load-bearing rubric the seed installer
migration writes against; if the engine output drifts from
expectations, the test fails before the seed reaches the DB.

The fixture population: 4 groups (A / B / C / D) × 5 members each,
with member 0 of each group set to tag2='Lead' (others 'Member').
20 reviewers and 20 reviewees, identical population on both sides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.services.rules.engine import evaluate
from app.services.rules.seeds import (
    SEED_CROSS_GROUP,
    SEED_FULL_MATRIX,
    SEED_INTRA_GROUP,
    SEED_SAME_GROUP_DIFFERENT_ROLE,
    SEED_THREE_REVIEWERS_PER_REVIEWEE,
    SEEDS,
)


@dataclass
class Reviewer:
    email: str
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None
    status: str = "active"
    id: int = 0


@dataclass
class Reviewee:
    email_or_identifier: str
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None
    status: str = "active"
    id: int = 0


_GROUPS = ("A", "B", "C", "D")
_MEMBERS_PER_GROUP = 5


def _build_population() -> tuple[list[Reviewer], list[Reviewee]]:
    reviewers: list[Reviewer] = []
    reviewees: list[Reviewee] = []
    next_id = 1
    for group in _GROUPS:
        for member in range(_MEMBERS_PER_GROUP):
            email = f"{group.lower()}{member:02d}@x.edu"
            tag2 = "Lead" if member == 0 else "Member"
            reviewers.append(
                Reviewer(
                    email=email,
                    tag_1=group,
                    tag_2=tag2,
                    id=next_id,
                )
            )
            reviewees.append(
                Reviewee(
                    email_or_identifier=email,
                    tag_1=group,
                    tag_2=tag2,
                    id=next_id,
                )
            )
            next_id += 1
    return reviewers, reviewees


def _emails(pairs: Iterable[tuple[object, object]]) -> set[tuple[str, str]]:
    return {
        (r.email, e.email_or_identifier) for r, e in pairs
    }


# ---------------------------------------------------------------------------
# Per-seed expected behaviour
# ---------------------------------------------------------------------------


def test_full_matrix_seed_pairs_everyone_excluding_self() -> None:
    reviewers, reviewees = _build_population()
    result = evaluate(
        SEED_FULL_MATRIX, reviewers=reviewers, reviewees=reviewees
    )
    # 20 × 20 = 400 candidates, minus 20 self-pairings.
    assert len(result.pairs) == 380
    assert result.excluded_counts.get("self_review") == 20


def test_intra_group_seed_pairs_within_group_only() -> None:
    reviewers, reviewees = _build_population()
    result = evaluate(
        SEED_INTRA_GROUP, reviewers=reviewers, reviewees=reviewees
    )
    # 4 groups × (5 × 5 - 5 self) = 4 × 20 = 80.
    assert len(result.pairs) == 80
    for r, e in result.pairs:
        assert r.tag_1 == e.tag_1
        assert r.email != e.email_or_identifier


def test_cross_group_seed_pairs_only_across_groups() -> None:
    reviewers, reviewees = _build_population()
    result = evaluate(
        SEED_CROSS_GROUP, reviewers=reviewers, reviewees=reviewees
    )
    # 20 reviewers × 15 cross-group reviewees = 300; no self-reviews
    # to subtract because reviewer's group always matches their own
    # email's group, so a same-email pair is also same-group and
    # already excluded by the `different_from` rule.
    assert len(result.pairs) == 300
    for r, e in result.pairs:
        assert r.tag_1 != e.tag_1


def test_same_group_different_role_seed() -> None:
    reviewers, reviewees = _build_population()
    result = evaluate(
        SEED_SAME_GROUP_DIFFERENT_ROLE,
        reviewers=reviewers,
        reviewees=reviewees,
    )
    # In each group: 1 Lead and 4 Members. Same-group AND
    # different-role pairs:
    # - Lead → 4 Members = 4
    # - 4 Members → 1 Lead = 4
    # Total per group = 8; × 4 groups = 32.
    assert len(result.pairs) == 32
    for r, e in result.pairs:
        assert r.tag_1 == e.tag_1
        assert r.tag_2 != e.tag_2


def test_three_reviewers_per_reviewee_seed() -> None:
    reviewers, reviewees = _build_population()
    result = evaluate(
        SEED_THREE_REVIEWERS_PER_REVIEWEE,
        reviewers=reviewers,
        reviewees=reviewees,
    )
    # Quota caps each reviewee at 3 reviewers; 20 reviewees × 3 = 60.
    assert len(result.pairs) == 60
    by_reviewee: dict[str, int] = {}
    for _, e in result.pairs:
        by_reviewee[e.email_or_identifier] = (
            by_reviewee.get(e.email_or_identifier, 0) + 1
        )
    assert all(count == 3 for count in by_reviewee.values())
    assert len(by_reviewee) == 20


def test_three_reviewers_seed_is_deterministic_across_runs() -> None:
    """Pinned seed (42) means two runs against the same population
    produce byte-identical pair sets."""

    reviewers, reviewees = _build_population()
    a = evaluate(
        SEED_THREE_REVIEWERS_PER_REVIEWEE,
        reviewers=reviewers,
        reviewees=reviewees,
    )
    b = evaluate(
        SEED_THREE_REVIEWERS_PER_REVIEWEE,
        reviewers=reviewers,
        reviewees=reviewees,
    )
    assert _emails(a.pairs) == _emails(b.pairs)


# ---------------------------------------------------------------------------
# Full Matrix equivalence pin (load-bearing for PR 8's retirement)
# ---------------------------------------------------------------------------


def test_full_matrix_seed_matches_generate_full_matrix() -> None:
    """The seeded ``Full Matrix`` RuleSet must produce the same pair
    set as ``assignments.generate_full_matrix(...)`` with
    ``exclude_self_review=True`` on the same population. This is the
    equivalence Segment 13A PR 8 leans on to retire the standalone
    Full Matrix card."""

    from app.services.assignments import generate_full_matrix

    reviewers, reviewees = _build_population()
    seed_result = evaluate(
        SEED_FULL_MATRIX, reviewers=reviewers, reviewees=reviewees
    )
    legacy_pairs, _ = generate_full_matrix(
        reviewers, reviewees, exclude_self_review=True
    )
    assert _emails(seed_result.pairs) == _emails(legacy_pairs)


# ---------------------------------------------------------------------------
# Library shape
# ---------------------------------------------------------------------------


def test_seeds_list_has_five_unique_names_in_install_order() -> None:
    names = [seed.name for seed in SEEDS]
    assert names == [
        "Full Matrix",
        "Intra-group peer review",
        "Cross-group peer review",
        "Same group, different role",
        "Three reviewers per reviewee",
    ]
    assert len(set(names)) == 5


def test_every_seed_is_marked_as_seed_scope() -> None:
    for seed in SEEDS:
        assert seed.scope.value == "seed"
        assert seed.metadata.isSeed is True
        assert seed.options.excludeSelfReviews is True
