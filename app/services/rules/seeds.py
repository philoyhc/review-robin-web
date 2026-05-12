"""Seeded RuleSets — Segment 13A PR 3, formalised in 15C Slice 1.

The five canonical seeds the spec names in §5.4. Definitions
live as Pydantic ``RuleSetSchema`` instances so they can be
validated at import time and round-tripped through the engine
before reaching the DB.

15C Slice 1 reframed these as the source of truth for
workspace-shipped seeds: they materialise into
``session_rule_sets`` (the per-session copy table) on session
create via :func:`materialise_seed_rule_sets`, mirroring
``ensure_default_response_type_definitions``. The historical
``rule_sets`` data migration (``9a7c2e1b4f60``) still imports
the legacy alias ``SEEDS`` from this module; the canonical
name is now ``SEEDED_RULE_SETS``.

Pinned guide: ``guide/archive/rules_table.md`` lays out each
canonical case in one row. The literals here are the byte-
equivalent ``RuleSetSchema`` realisation.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionRuleSet
from app.schemas.rules import (
    Combinator,
    MatchRule,
    Predicate,
    QuotaRule,
    QuotaScope,
    QuotaSelection,
    RuleSetMetadata,
    RuleSetOptions,
    RuleSetSchema,
    RuleSetScope,
    SelectionStrategy,
)


SEED_FULL_MATRIX: Final[RuleSetSchema] = RuleSetSchema(
    name="Full Matrix",
    description="Pair every reviewer with every reviewee.",
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[],
    options=RuleSetOptions(excludeSelfReviews=False, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


SEED_INTRA_GROUP: Final[RuleSetSchema] = RuleSetSchema(
    name="Intra-group peer review",
    description="Reviewer and reviewee share tag1.",
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[
        MatchRule(
            id="same_tag1",
            predicate=Predicate(
                field="reviewer.tag1",
                operator="same_as",
                operand="reviewee.tag1",
            ),
        )
    ],
    options=RuleSetOptions(excludeSelfReviews=False, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


SEED_CROSS_GROUP: Final[RuleSetSchema] = RuleSetSchema(
    name="Cross-group peer review",
    description=(
        "Reviewer and reviewee have different tag1 — useful for "
        "fresh-perspective rounds."
    ),
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[
        MatchRule(
            id="diff_tag1",
            predicate=Predicate(
                field="reviewer.tag1",
                operator="different_from",
                operand="reviewee.tag1",
            ),
        )
    ],
    options=RuleSetOptions(excludeSelfReviews=False, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


SEED_SAME_GROUP_DIFFERENT_ROLE: Final[RuleSetSchema] = RuleSetSchema(
    name="Same group, different role",
    description=(
        "Same tag1, different tag2. Pair within the team but never "
        "with someone of the same role."
    ),
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[
        MatchRule(
            id="same_tag1",
            predicate=Predicate(
                field="reviewer.tag1",
                operator="same_as",
                operand="reviewee.tag1",
            ),
        ),
        MatchRule(
            id="diff_tag2",
            predicate=Predicate(
                field="reviewer.tag2",
                operator="different_from",
                operand="reviewee.tag2",
            ),
        ),
    ],
    options=RuleSetOptions(excludeSelfReviews=False, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


SEED_THREE_REVIEWERS_PER_REVIEWEE: Final[RuleSetSchema] = RuleSetSchema(
    name="Three reviewers per reviewee",
    description=(
        "Full candidate pool, then a PER_REVIEWEE quota of "
        "min=3, max=3, random with a fixed seed."
    ),
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[
        QuotaRule(
            id="three_each",
            scope=QuotaScope.PER_REVIEWEE,
            min=3,
            max=3,
            selection=QuotaSelection(
                strategy=SelectionStrategy.RANDOM, seed=42
            ),
        )
    ],
    options=RuleSetOptions(excludeSelfReviews=False, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


# Order matters: drives the order seeds appear in the picker
# (per-session ``session_rule_sets.id`` ascending, which mirrors
# this list's order at materialise-time).
SEEDED_RULE_SETS: Final[list[RuleSetSchema]] = [
    SEED_FULL_MATRIX,
    SEED_INTRA_GROUP,
    SEED_CROSS_GROUP,
    SEED_SAME_GROUP_DIFFERENT_ROLE,
    SEED_THREE_REVIEWERS_PER_REVIEWEE,
]

# Backwards-compat alias for the historical ``9a7c2e1b4f60`` Alembic
# data migration. Do not introduce new readers of this name —
# everything else uses ``SEEDED_RULE_SETS``.
SEEDS: Final[list[RuleSetSchema]] = SEEDED_RULE_SETS


def _rules_json_payload(schema: RuleSetSchema) -> list[dict[str, Any]]:
    """Serialise a ``RuleSetSchema``'s rule list to the JSON shape
    ``session_rule_sets.rules_json`` expects — same shape as
    ``rule_set_revisions.rules_json`` on the library side."""
    return [rule.model_dump(mode="json", by_alias=True) for rule in schema.rules]


def materialise_seed_rule_sets(
    db: Session, review_session: ReviewSession
) -> dict[str, SessionRuleSet]:
    """Idempotently materialise every workspace-shipped seed into
    ``session_rule_sets`` for the given session. Returns a dict keyed
    by ``name`` covering every seeded row currently in the DB for the
    session.

    Re-running on a session that already has the seeds is a no-op —
    pre-existing rows (matched by ``(session_id, name)``) are left
    untouched, including any operator edits to their snapshot.
    Mirrors :func:`app.services.instruments._rtds.ensure_default_response_type_definitions`.

    The audit emitter ``session_rule_sets.materialised_from_seed``
    is **not** fired from here; callers that want the event (e.g.
    ``sessions.create_session``) call :func:`audit.write_event`
    explicitly with the returned dict to compute the new-row count.
    """
    existing = {
        row.name: row
        for row in db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
    }

    added = False
    for schema in SEEDED_RULE_SETS:
        if schema.name in existing:
            continue
        row = SessionRuleSet(
            session_id=review_session.id,
            name=schema.name,
            description=schema.description or "",
            combinator=schema.combinator.value,
            exclude_self_reviews=schema.options.excludeSelfReviews,
            seed=schema.options.seed,
            rules_json=_rules_json_payload(schema),
            library_origin_id=None,
            is_seeded=True,
        )
        db.add(row)
        existing[schema.name] = row
        added = True

    if added:
        db.flush()

    return existing
