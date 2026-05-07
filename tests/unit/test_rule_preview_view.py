"""Unit tests for ``app/services/rules/preview.py`` — Segment 13A
PR 7.

Pure transform: pass a synthetic ``EvaluationResult`` through
``build_preview`` and assert the distribution buckets / sampled
pairs / warnings render as expected.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.rules.engine import EvaluationResult
from app.services.rules.preview import (
    DistributionBucket,
    SampledPair,
    build_preview,
)


@dataclass
class _Reviewer:
    email: str


@dataclass
class _Reviewee:
    email_or_identifier: str


def _make_pairs(spec: list[tuple[str, str]]) -> list[tuple[object, object]]:
    return [(_Reviewer(email=r), _Reviewee(email_or_identifier=e)) for r, e in spec]


def test_pair_count_reflects_total_pairs() -> None:
    pairs = _make_pairs([("a@x", "b@x"), ("a@x", "c@x"), ("d@x", "b@x")])
    preview = build_preview(
        result=EvaluationResult(pairs=pairs),
        reviewer_count=2,
        reviewee_count=2,
    )
    assert preview.pair_count == 3


def test_per_reviewer_distribution_buckets_by_count() -> None:
    """Reviewers with 2 pairs vs 1 pair vs 0 pairs land in three
    buckets sorted by pair-count descending."""

    pairs = _make_pairs(
        [
            ("a@x", "x1@x"), ("a@x", "x2@x"),  # a → 2 pairs
            ("b@x", "x1@x"),                    # b → 1 pair
            # c reviewer has no pairs
        ]
    )
    preview = build_preview(
        result=EvaluationResult(pairs=pairs),
        reviewer_count=3,
        reviewee_count=2,
    )
    assert preview.distribution_per_reviewer == [
        DistributionBucket(individuals=1, pair_count=2),
        DistributionBucket(individuals=1, pair_count=1),
        DistributionBucket(individuals=1, pair_count=0),
    ]


def test_sampled_pairs_caps_at_ten_in_evaluation_order() -> None:
    pairs = _make_pairs(
        [(f"r{i:02d}@x", f"e{i:02d}@x") for i in range(15)]
    )
    preview = build_preview(
        result=EvaluationResult(pairs=pairs),
        reviewer_count=15,
        reviewee_count=15,
    )
    assert len(preview.sampled_pairs) == 10
    assert preview.sampled_pairs[0] == SampledPair(
        reviewer_email="r00@x", reviewee_identifier="e00@x"
    )
    assert preview.sampled_pairs[-1] == SampledPair(
        reviewer_email="r09@x", reviewee_identifier="e09@x"
    )


def test_empty_population_yields_empty_preview() -> None:
    preview = build_preview(
        result=EvaluationResult(pairs=[]),
        reviewer_count=0,
        reviewee_count=5,
    )
    assert preview.populations_empty is True
    assert preview.distribution_per_reviewer == []
    assert preview.distribution_per_reviewee == []
    assert preview.sampled_pairs == []


def test_warnings_pass_through_from_evaluation_result() -> None:
    preview = build_preview(
        result=EvaluationResult(
            pairs=[],
            warnings=["RuleSet produced zero assignments"],
        ),
        reviewer_count=2,
        reviewee_count=2,
    )
    assert preview.warnings == ["RuleSet produced zero assignments"]


def test_distribution_groups_individuals_at_the_same_count() -> None:
    """Three reviewers each with 1 pair produce one bucket of
    ``individuals=3, pair_count=1``."""

    pairs = _make_pairs(
        [("a@x", "x@x"), ("b@x", "x@x"), ("c@x", "x@x")]
    )
    preview = build_preview(
        result=EvaluationResult(pairs=pairs),
        reviewer_count=3,
        reviewee_count=1,
    )
    assert preview.distribution_per_reviewer == [
        DistributionBucket(individuals=3, pair_count=1),
    ]
    # Reviewee got 3 pairs (one per reviewer).
    assert preview.distribution_per_reviewee == [
        DistributionBucket(individuals=1, pair_count=3),
    ]
