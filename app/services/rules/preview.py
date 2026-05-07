"""Live preview view-shape for the Rule Based editor — Segment 13A
PR 7.

Builds a ``RulePreview`` dataclass from an ``EvaluationResult``
plus the engine's ``ValidationIssue`` list. The editor template
renders it on initial load (synchronously) and the JS hook in the
editor refetches it after each form-element change so operators
see the impact of an edit before clicking Save / Save As.

Pure transform — no DB access, no audit writes. The preview is a
read-only surface; running it 100 times produces no audit churn.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.services.rules.engine import EvaluationResult


_PAIR_SAMPLE_LIMIT = 10


@dataclass(frozen=True)
class DistributionBucket:
    """One row in the per-reviewer or per-reviewee distribution.

    ``pair_count`` is the number of pairs at this bucket (each
    individual sees the same total because we group by count); the
    template renders these as "N reviewers → K pairs each"."""

    individuals: int
    pair_count: int


@dataclass(frozen=True)
class SampledPair:
    reviewer_email: str
    reviewee_identifier: str


@dataclass(frozen=True)
class RulePreview:
    pair_count: int
    """Total pairs the RuleSet would produce against the session's
    current populations."""

    distribution_per_reviewer: list[DistributionBucket]
    distribution_per_reviewee: list[DistributionBucket]
    sampled_pairs: list[SampledPair]
    warnings: list[str]
    populations_empty: bool
    """True when reviewer or reviewee population is empty — the
    template renders a "configure populations first" hint instead
    of zero-distribution noise."""


def _bucket_distribution(
    counts: Counter[str],
    total_individuals: int,
) -> list[DistributionBucket]:
    """Group identifiers by pair-count and emit buckets sorted by
    pair-count descending. Identifiers absent from ``counts`` are
    counted as zero-pair buckets."""

    if total_individuals == 0:
        return []
    individuals_at_count: Counter[int] = Counter()
    for pair_count in counts.values():
        individuals_at_count[pair_count] += 1
    represented = sum(individuals_at_count.values())
    zero_count = total_individuals - represented
    if zero_count > 0:
        individuals_at_count[0] += zero_count
    buckets = [
        DistributionBucket(individuals=individuals, pair_count=pair_count)
        for pair_count, individuals in individuals_at_count.items()
    ]
    buckets.sort(key=lambda b: (-b.pair_count, -b.individuals))
    return buckets


def build_preview(
    *,
    result: EvaluationResult,
    reviewer_count: int,
    reviewee_count: int,
) -> RulePreview:
    """Compose the editor's right-column preview from an
    ``engine.evaluate(...)`` outcome. ``reviewer_count`` /
    ``reviewee_count`` are the session's full population sizes
    (so zero-pair individuals appear in the distribution)."""

    populations_empty = reviewer_count == 0 or reviewee_count == 0

    if populations_empty:
        return RulePreview(
            pair_count=0,
            distribution_per_reviewer=[],
            distribution_per_reviewee=[],
            sampled_pairs=[],
            warnings=list(result.warnings) if result.warnings else [],
            populations_empty=True,
        )

    reviewer_counts: Counter[str] = Counter()
    reviewee_counts: Counter[str] = Counter()
    for reviewer, reviewee in result.pairs:
        reviewer_email = getattr(reviewer, "email", None) or ""
        reviewee_identifier = (
            getattr(reviewee, "email_or_identifier", None) or ""
        )
        if reviewer_email:
            reviewer_counts[reviewer_email] += 1
        if reviewee_identifier:
            reviewee_counts[reviewee_identifier] += 1

    sample = []
    for reviewer, reviewee in result.pairs[:_PAIR_SAMPLE_LIMIT]:
        sample.append(
            SampledPair(
                reviewer_email=getattr(reviewer, "email", "") or "",
                reviewee_identifier=(
                    getattr(reviewee, "email_or_identifier", "") or ""
                ),
            )
        )

    return RulePreview(
        pair_count=len(result.pairs),
        distribution_per_reviewer=_bucket_distribution(
            reviewer_counts, reviewer_count
        ),
        distribution_per_reviewee=_bucket_distribution(
            reviewee_counts, reviewee_count
        ),
        sampled_pairs=sample,
        warnings=list(result.warnings),
        populations_empty=False,
    )
