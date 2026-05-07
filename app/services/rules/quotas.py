"""Quota-rule application.

Quotas constrain the **multiplicity** of assignments along an axis
(``PER_REVIEWER`` or ``PER_REVIEWEE``). They cap the number of pairs
that survive after the content rules have run; they do not select
pairs by content. See ``spec/rule_based_assignment.md`` §4.7.

Two selection strategies cover the cases this segment ships:

- ``RANDOM`` — seeded reproducible random sampling. The seed comes
  from the quota rule's own ``selection.seed`` if set; otherwise from
  the RuleSet's ``options.seed`` (the global seed); otherwise from a
  hash of the RuleSet's current revision id (passed in by the caller).
- ``ROUND_ROBIN`` — deterministic, no randomness; iterates the axis
  in sorted order and picks the first ``max`` candidates per axis-key.

Both strategies are deterministic for a given ``(pairs, rule, seed)``
triple — same inputs always produce the same outputs in the same
order. This is the engine's overall determinism guarantee surfaced at
the quota level.
"""

from __future__ import annotations

import random
from collections import defaultdict

from app.schemas.rules import QuotaRule, QuotaScope, SelectionStrategy


def _axis_key(
    rule: QuotaRule,
    pair: tuple[object, object],
) -> object:
    """The axis a pair is grouped under for the quota."""

    reviewer, reviewee = pair
    if rule.scope == QuotaScope.PER_REVIEWER:
        return getattr(reviewer, "email", None)
    return getattr(reviewee, "email_or_identifier", None)


def _stable_pair_sort_key(
    pair: tuple[object, object],
) -> tuple[str, str]:
    reviewer, reviewee = pair
    return (
        getattr(reviewer, "email", "") or "",
        getattr(reviewee, "email_or_identifier", "") or "",
    )


def apply_quota(
    pairs: list[tuple[object, object]],
    rule: QuotaRule,
    *,
    fallback_seed: int,
) -> tuple[list[tuple[object, object]], int, list[str]]:
    """Apply ``rule`` to ``pairs``, returning
    ``(surviving_pairs, excluded_count, warnings)``.

    ``fallback_seed`` is consulted only by ``RANDOM`` selections that
    don't carry their own seed and where the RuleSet doesn't supply
    one either. Callers in ``engine.py`` compose this from
    ``options.seed`` or a hash of the revision id.
    """

    grouped: dict[object, list[tuple[object, object]]] = defaultdict(list)
    for pair in pairs:
        grouped[_axis_key(rule, pair)].append(pair)

    selected: list[tuple[object, object]] = []
    warnings: list[str] = []
    excluded = 0

    seed = (
        rule.selection.seed
        if rule.selection.seed is not None
        else fallback_seed
    )

    for axis_key in sorted(grouped, key=lambda k: ("" if k is None else str(k))):
        axis_pairs = sorted(grouped[axis_key], key=_stable_pair_sort_key)
        cap = rule.max if rule.max is not None else len(axis_pairs)

        if rule.selection.strategy == SelectionStrategy.RANDOM:
            rng = random.Random(f"{seed}::{axis_key}")
            chosen_indices = sorted(
                rng.sample(range(len(axis_pairs)), min(cap, len(axis_pairs)))
            )
            kept = [axis_pairs[i] for i in chosen_indices]
        else:  # ROUND_ROBIN
            kept = axis_pairs[:cap]

        if rule.min is not None and len(axis_pairs) < rule.min:
            warnings.append(
                f"quota rule {rule.id!r}: only {len(axis_pairs)} candidate "
                f"pair(s) for {rule.scope.value} key {axis_key!r}; "
                f"minimum {rule.min} not met"
            )

        excluded += len(axis_pairs) - len(kept)
        selected.extend(kept)

    selected.sort(key=_stable_pair_sort_key)
    return selected, excluded, warnings
