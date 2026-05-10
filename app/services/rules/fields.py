"""Operator-facing predicate field names → ORM attribute mapping.

The single source of truth for the dotted-form vocabulary the rule
engine, the editor's field picker, and the editor's operand picker
all read from. Per
``guide/segment_13A_rulebased_assignment_builder.md`` §"Predicate
vocabulary mapping": adding a new addressable field is a one-row edit
here and nowhere else.

The dotted form (``reviewer.tag1``) is what stores in
``rule_set_revisions.rules_json`` and what operators see in the
editor. The ORM attribute (``tag_1``) is the implementation detail the
engine uses to read the value off a ``Reviewer`` / ``Reviewee`` row.

Segment 15D PR 3 added the ``pair_context.tag1/2/3`` family. Their
values live on the new ``relationships`` table (one row per
``(session_id, reviewer_id, reviewee_id)`` pair). 15D PR 4 wires
the engine to consult an eager-loaded
``pair_context_lookup: dict[tuple[int, int], Relationship]`` map
keyed on ``(reviewer_id, reviewee_id)``. The engine binds the
lookup via ``set_pair_context_lookup`` for the duration of an
``evaluate()`` call; ``get_field_value`` reads it through a
``ContextVar``. Inactive rows (``status != "active"``) are
skipped at lookup time — pair_context predicates evaluate as if
the row didn't exist (return ``None``), per the locked
"skip-at-lookup" semantic.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from app.db.models import Relationship

# (side, attribute) tuple per dotted field name. ``side`` is
# ``"reviewer"`` / ``"reviewee"`` / ``"pair_context"``; ``attribute``
# is the ORM column attribute on the corresponding model.
FIELD_MAP: Final[dict[str, tuple[str, str]]] = {
    "reviewer.email": ("reviewer", "email"),
    "reviewer.tag1": ("reviewer", "tag_1"),
    "reviewer.tag2": ("reviewer", "tag_2"),
    "reviewer.tag3": ("reviewer", "tag_3"),
    "reviewee.email": ("reviewee", "email_or_identifier"),
    "reviewee.tag1": ("reviewee", "tag_1"),
    "reviewee.tag2": ("reviewee", "tag_2"),
    "reviewee.tag3": ("reviewee", "tag_3"),
    "pair_context.tag1": ("pair_context", "tag_1"),
    "pair_context.tag2": ("pair_context", "tag_2"),
    "pair_context.tag3": ("pair_context", "tag_3"),
}


def parse_field(dotted: str) -> tuple[str, str]:
    """Resolve a dotted field name to ``(side, orm_attribute)``.

    Raises ``KeyError`` on unknown names. Callers should validate via
    ``app/schemas/rules.py::ALLOWED_PREDICATE_FIELDS`` before reaching
    here, but the lookup raises explicitly so a programmer error
    surfaces fast.
    """

    if dotted not in FIELD_MAP:
        raise KeyError(f"unknown predicate field: {dotted!r}")
    return FIELD_MAP[dotted]


# Context-bound ``(reviewer_id, reviewee_id) -> Relationship`` lookup
# the engine populates for the duration of one ``evaluate()`` call.
# A ``ContextVar`` keeps the predicate-eval API ergonomic (no
# threading the lookup through every operator), and resets cleanly
# when ``evaluate()`` exits even if it raises.
_pair_context_lookup: ContextVar[
    dict[tuple[int, int], "Relationship"] | None
] = ContextVar("pair_context_lookup", default=None)


def set_pair_context_lookup(
    lookup: dict[tuple[int, int], "Relationship"] | None,
) -> object:
    """Bind a pair-context lookup for the calling task. Returns a
    token the caller passes to ``reset_pair_context_lookup`` when
    done. Engine call sites use this in a try/finally pair around
    ``evaluate()``."""

    return _pair_context_lookup.set(lookup)


def reset_pair_context_lookup(token: object) -> None:
    _pair_context_lookup.reset(token)  # type: ignore[arg-type]


def get_field_value(
    dotted: str, *, reviewer: object, reviewee: object
) -> str | None:
    """Return the value of ``dotted`` for the given pair.

    Empty strings normalise to ``None`` per spec §9 (empty tag values
    are treated as missing). The engine relies on this so predicates
    referencing a missing field consistently evaluate to ``false``
    unless the operator is ``is_empty``.

    For ``pair_context.*`` fields the lookup is the context-bound
    ``(reviewer_id, reviewee_id) -> Relationship`` map populated by
    ``engine.evaluate()`` for the duration of its run. Inactive rows
    (``status != "active"``) are skipped at lookup time — predicates
    referencing pair-context evaluate as if no row exists for the
    pair (return ``None``).
    """

    side, attribute = parse_field(dotted)
    if side == "pair_context":
        return _resolve_pair_context(reviewer, reviewee, attribute)
    target = reviewer if side == "reviewer" else reviewee
    raw = getattr(target, attribute, None)
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() == "":
        return None
    return raw


def _resolve_pair_context(
    reviewer: object, reviewee: object, attribute: str
) -> str | None:
    lookup = _pair_context_lookup.get()
    if lookup is None:
        return None
    reviewer_id = getattr(reviewer, "id", None)
    reviewee_id = getattr(reviewee, "id", None)
    if reviewer_id is None or reviewee_id is None:
        return None
    relationship = lookup.get((reviewer_id, reviewee_id))
    if relationship is None:
        return None
    if getattr(relationship, "status", None) != "active":
        # Skip-at-lookup: inactive rows hide their tag values from
        # predicates. The pair stays in the candidate set; reviewer /
        # reviewee tag rules still see it.
        return None
    raw = getattr(relationship, attribute, None)
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() == "":
        return None
    return raw
