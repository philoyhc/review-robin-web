"""Pure-Python rule-engine evaluator for the Advanced (RuleBased)
assignment mode.

Two top-level functions:

- ``evaluate(rule_set, *, reviewers, reviewees, ...)`` — runs the
  RuleSet against the populations and returns the surviving pairs
  alongside exclusion counts and warnings.
- ``validate_rule_set(rule_set, reviewers, reviewees)`` — returns a
  list of structural / population issues without producing pairs.
  Used by the editor's live preview (Segment 13A PR 7) on every
  keystroke.

The evaluator is **pure**: no DB calls, no time reads, no side
effects. Callers (``replace_assignments``) take the returned pairs
and write them.

The evaluator is **deterministic**: same inputs always produce the
same pairs in the same order. RANDOM-strategy quotas seed from
``options.seed`` if set, otherwise from the caller-supplied
``revision_seed`` so two evaluations against the same revision are
identical. See ``app/services/rules/quotas.py`` for the per-quota
seeding rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.schemas.rules import (
    Combinator,
    CompositeOp,
    CompositeRule,
    FilterRule,
    MatchRule,
    QuotaRule,
    RuleSetSchema,
)
from app.services.rules.predicates import evaluate_predicate
from app.services.rules.quotas import apply_quota


# ---------------------------------------------------------------------------
# Result + issue dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationResult:
    """Output of a single ``evaluate(...)`` run."""

    pairs: list[tuple[object, object]]
    """Surviving assignments in deterministic
    ``(reviewer.email, reviewee.email_or_identifier)`` order."""

    excluded_counts: dict[str, int] = field(default_factory=dict)
    """Exclusion reasons, flatten-keyed for the
    ``assignments.generated.context.excluded_*`` audit shape per
    Segment 11K. Keys: ``self_review``, ``predicate.<rule_id>``,
    ``quota.per_reviewer``, ``quota.per_reviewee``."""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal observations — zero-assignment outcomes,
    quota under-min satisfaction, etc."""


@dataclass(frozen=True)
class ValidationIssue:
    """A structural or population-level problem with the RuleSet.

    Surfaced by the editor (PR 5) and by ``validate_rule_set`` (PR 7's
    live preview). Not raised — collected so a single save can show
    every problem at once."""

    rule_id: str | None
    message: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate(
    rule_set: RuleSetSchema,
    *,
    reviewers: Iterable[object],
    reviewees: Iterable[object],
    override_exclude_self_reviews: bool | None = None,
    revision_seed: int = 0,
) -> EvaluationResult:
    """Run ``rule_set`` against the populations and return the result."""

    reviewers_list = list(reviewers)
    reviewees_list = list(reviewees)

    candidates: list[tuple[object, object]] = [
        (r, e) for r in reviewers_list for e in reviewees_list
    ]
    candidates.sort(key=_pair_sort_key)

    excluded_counts: dict[str, int] = {}
    warnings: list[str] = []

    # Step 2 — self-review desugar.
    exclude_self = (
        override_exclude_self_reviews
        if override_exclude_self_reviews is not None
        else rule_set.options.excludeSelfReviews
    )
    if exclude_self:
        survivors: list[tuple[object, object]] = []
        for pair in candidates:
            if _is_self_review(*pair):
                excluded_counts["self_review"] = (
                    excluded_counts.get("self_review", 0) + 1
                )
            else:
                survivors.append(pair)
        candidates = survivors

    # Step 3 — partition rules into content vs quota.
    content_rules: list[FilterRule | MatchRule | CompositeRule] = []
    quota_rules: list[QuotaRule] = []
    for rule in rule_set.rules:
        if not rule.enabled:
            continue
        if isinstance(rule, QuotaRule):
            quota_rules.append(rule)
        else:
            content_rules.append(rule)

    # Step 4 — apply content rules per the top-level combinator.
    survivors, content_excluded = _apply_content_rules(
        candidates,
        content_rules,
        combinator=rule_set.combinator,
    )
    for key, count in content_excluded.items():
        excluded_counts[key] = excluded_counts.get(key, 0) + count

    # Step 5 — apply quota rules in declaration order.
    fallback_seed = (
        rule_set.options.seed
        if rule_set.options.seed is not None
        else revision_seed
    )
    for quota in quota_rules:
        survivors, quota_excluded, quota_warnings = apply_quota(
            survivors, quota, fallback_seed=fallback_seed
        )
        if quota_excluded:
            key = (
                "quota.per_reviewer"
                if quota.scope.value == "PER_REVIEWER"
                else "quota.per_reviewee"
            )
            excluded_counts[key] = (
                excluded_counts.get(key, 0) + quota_excluded
            )
        warnings.extend(quota_warnings)

    # Step 6 — emit pairs in deterministic order. (``apply_quota``
    # already sorts; the no-quota path inherits the candidate sort
    # above.)
    if not quota_rules:
        survivors.sort(key=_pair_sort_key)

    if not survivors:
        warnings.append("RuleSet produced zero assignments")

    return EvaluationResult(
        pairs=survivors,
        excluded_counts=excluded_counts,
        warnings=warnings,
    )


def validate_rule_set(
    rule_set: RuleSetSchema,
    reviewers: Iterable[object] | None = None,
    reviewees: Iterable[object] | None = None,
) -> list[ValidationIssue]:
    """Check ``rule_set`` for structural and (when populations are
    supplied) population-level issues.

    Structural checks rely on the Pydantic validators that already run
    at ``model_validate`` time, so this function focuses on the
    things those can't catch: zero-rule RuleSets, unreferenced quotas
    under impossible populations, etc. Both arguments default to
    ``None`` so the editor can call this with just a RuleSet during
    early authoring."""

    issues: list[ValidationIssue] = []

    if not rule_set.rules and not rule_set.options.excludeSelfReviews:
        issues.append(
            ValidationIssue(
                rule_id=None,
                message=(
                    "RuleSet has no rules and self-review is not "
                    "excluded — every (reviewer, reviewee) pair will "
                    "be emitted"
                ),
            )
        )

    if reviewers is not None and reviewees is not None:
        reviewers_list = list(reviewers)
        reviewees_list = list(reviewees)
        if not reviewers_list:
            issues.append(
                ValidationIssue(
                    rule_id=None, message="reviewer population is empty"
                )
            )
        if not reviewees_list:
            issues.append(
                ValidationIssue(
                    rule_id=None, message="reviewee population is empty"
                )
            )
        for rule in rule_set.rules:
            if isinstance(rule, QuotaRule):
                axis_size = (
                    len(reviewees_list)
                    if rule.scope.value == "PER_REVIEWEE"
                    else len(reviewers_list)
                )
                if rule.min is not None and rule.min > axis_size:
                    issues.append(
                        ValidationIssue(
                            rule_id=rule.id,
                            message=(
                                f"quota min ({rule.min}) exceeds "
                                f"{rule.scope.value} population size "
                                f"({axis_size})"
                            ),
                        )
                    )

    return issues


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pair_sort_key(pair: tuple[object, object]) -> tuple[str, str]:
    reviewer, reviewee = pair
    return (
        (getattr(reviewer, "email", "") or "").lower(),
        (getattr(reviewee, "email_or_identifier", "") or "").lower(),
    )


def _is_self_review(reviewer: object, reviewee: object) -> bool:
    a = (getattr(reviewer, "email", "") or "").strip().lower()
    b = (
        getattr(reviewee, "email_or_identifier", "") or ""
    ).strip().lower()
    if not a or not b:
        return False
    return a == b


def _apply_content_rules(
    candidates: list[tuple[object, object]],
    rules: list[FilterRule | MatchRule | CompositeRule],
    *,
    combinator: Combinator,
) -> tuple[list[tuple[object, object]], dict[str, int]]:
    """Apply the content rules to ``candidates`` per the combinator.

    Returns ``(surviving_pairs, excluded_counts_by_rule_id)``.
    """

    excluded_counts: dict[str, int] = {}

    if not rules:
        return candidates, excluded_counts

    if combinator == Combinator.ALL_OF:
        survivors = candidates
        for rule in rules:
            survivors, dropped = _apply_one_content_rule(survivors, rule)
            if dropped:
                excluded_counts[f"predicate.{rule.id}"] = dropped
        return survivors, excluded_counts

    if combinator == Combinator.ANY_OF:
        # Union of allowed sets across rules. A pair is kept if at
        # least one rule includes it.
        kept: dict[tuple[str, str], tuple[object, object]] = {}
        for rule in rules:
            included, _ = _apply_one_content_rule(candidates, rule)
            for pair in included:
                kept[_pair_sort_key(pair)] = pair
        survivors = [kept[k] for k in sorted(kept)]
        excluded_counts["predicate.any_of"] = len(candidates) - len(survivors)
        if excluded_counts["predicate.any_of"] == 0:
            excluded_counts.pop("predicate.any_of")
        return survivors, excluded_counts

    # PIPELINE — apply rules in order; each rule may add to or remove
    # from the working set. FILTER drops; MATCH/COMPOSITE keep matching
    # pairs and re-add any candidate that matched even if a previous
    # FILTER removed it. Last-writer-wins per pair.
    working: dict[tuple[str, str], tuple[object, object]] = {
        _pair_sort_key(p): p for p in candidates
    }
    for rule in rules:
        if isinstance(rule, FilterRule):
            for pair in list(working.values()):
                if _content_rule_matches(rule, pair):
                    key = _pair_sort_key(pair)
                    if key in working:
                        excluded_counts[f"predicate.{rule.id}"] = (
                            excluded_counts.get(f"predicate.{rule.id}", 0) + 1
                        )
                        working.pop(key, None)
        else:
            for pair in candidates:
                if _content_rule_matches(rule, pair):
                    working[_pair_sort_key(pair)] = pair
    return [working[k] for k in sorted(working)], excluded_counts


def _apply_one_content_rule(
    candidates: list[tuple[object, object]],
    rule: FilterRule | MatchRule | CompositeRule,
) -> tuple[list[tuple[object, object]], int]:
    """Return ``(included_pairs, dropped_count)`` for ``rule`` against
    the candidate list.

    Semantics per spec §4.2:
    - **FILTER** removes pairs that match the predicate.
    - **MATCH** keeps pairs that match the predicate.
    - **COMPOSITE** evaluates its child rules under the boolean op.
    """

    included: list[tuple[object, object]] = []
    for pair in candidates:
        if _content_rule_matches(rule, pair):
            if isinstance(rule, FilterRule):
                continue
            included.append(pair)
        else:
            if isinstance(rule, FilterRule):
                included.append(pair)
    dropped = len(candidates) - len(included)
    return included, dropped


def _content_rule_matches(
    rule: FilterRule | MatchRule | CompositeRule,
    pair: tuple[object, object],
) -> bool:
    """``True`` iff the rule's predicate (or composite expression)
    matches the pair. The semantic difference between FILTER and MATCH
    is in the *caller* (``_apply_one_content_rule``); here both kinds
    use predicate truthiness identically."""

    reviewer, reviewee = pair
    if isinstance(rule, (FilterRule, MatchRule)):
        return evaluate_predicate(
            rule.predicate, reviewer=reviewer, reviewee=reviewee
        )

    # Composite: AND / OR / NOT over child rule truthiness.
    child_results = [_content_rule_matches(child, pair) for child in rule.rules]
    if rule.op == CompositeOp.AND:
        return all(child_results)
    if rule.op == CompositeOp.OR:
        return any(child_results)
    # NOT — by spec a unary operator; if multiple children, NOT-ALL
    # (i.e. negate the AND).
    return not all(child_results)
