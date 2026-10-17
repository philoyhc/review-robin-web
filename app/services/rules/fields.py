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

``reviewer.pair_tag1/2/3`` and ``reviewee.pair_tag1/2/3`` (author,
2026-10-17; ``guide/assignment_rule_clarify.md`` Item 2) read the same
relationship tags as a *person's* tag: every value the reviewer (or the
reviewee) holds in that slot across their active pairs, whoever the
other side is. They are multi-valued, so predicates read them through
:func:`get_field_values`; ``pair_context.tagN`` stays the per-pair
reading.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from app.db.models import Relationship

# (side, attribute) tuple per dotted field name. ``side`` is
# ``"reviewer"`` / ``"reviewee"`` / ``"pair_context"`` for a single
# value off one row, or ``"reviewer_pairs"`` / ``"reviewee_pairs"`` for
# a person's values across their relationships; ``attribute`` is the
# ORM column attribute (on ``Relationship`` for the last three).
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
    "reviewer.pair_tag1": ("reviewer_pairs", "tag_1"),
    "reviewer.pair_tag2": ("reviewer_pairs", "tag_2"),
    "reviewer.pair_tag3": ("reviewer_pairs", "tag_3"),
    "reviewee.pair_tag1": ("reviewee_pairs", "tag_1"),
    "reviewee.pair_tag2": ("reviewee_pairs", "tag_2"),
    "reviewee.pair_tag3": ("reviewee_pairs", "tag_3"),
}

_PERSON_SIDES: Final[frozenset[str]] = frozenset({"reviewer_pairs", "reviewee_pairs"})


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

# ``(side, person_id, attribute) -> values`` over the bound lookup's
# active rows, built once per bind so a person-level field costs a dict
# read per pair rather than a scan.
_PersonIndex = dict[tuple[str, int, str], frozenset[str]]
_person_index: ContextVar[_PersonIndex | None] = ContextVar(
    "pair_context_person_index", default=None
)


def _build_person_index(
    lookup: dict[tuple[int, int], "Relationship"] | None,
) -> _PersonIndex:
    collected: dict[tuple[str, int, str], set[str]] = {}
    for (reviewer_id, reviewee_id), relationship in (lookup or {}).items():
        if getattr(relationship, "status", None) != "active":
            continue
        for attribute in ("tag_1", "tag_2", "tag_3"):
            raw = getattr(relationship, attribute, None)
            if raw is None or not str(raw).strip():
                continue
            for key in (
                ("reviewer_pairs", reviewer_id, attribute),
                ("reviewee_pairs", reviewee_id, attribute),
            ):
                collected.setdefault(key, set()).add(raw)
    return {key: frozenset(values) for key, values in collected.items()}


def set_pair_context_lookup(
    lookup: dict[tuple[int, int], "Relationship"] | None,
) -> object:
    """Bind a pair-context lookup for the calling task. Returns a
    token the caller passes to ``reset_pair_context_lookup`` when
    done. Engine call sites use this in a try/finally pair around
    ``evaluate()``."""

    return (
        _pair_context_lookup.set(lookup),
        _person_index.set(_build_person_index(lookup)),
    )


def reset_pair_context_lookup(token: object) -> None:
    lookup_token, index_token = token  # type: ignore[misc]
    _person_index.reset(index_token)
    _pair_context_lookup.reset(lookup_token)


def get_field_value(
    dotted: str, *, reviewer: object, reviewee: object
) -> str | None:
    """Return the value of ``dotted`` for the given pair.

    Empty strings normalise to ``None`` per spec §9 (empty tag values
    are treated as missing). The engine relies on this so every
    operator sees one notion of "no value"; what each does with it is in
    ``app/services/rules/predicates.py``.

    For ``pair_context.*`` fields the lookup is the context-bound
    ``(reviewer_id, reviewee_id) -> Relationship`` map populated by
    ``engine.evaluate()`` for the duration of its run. Inactive rows
    (``status != "active"``) are skipped at lookup time — predicates
    referencing pair-context evaluate as if no row exists for the
    pair (return ``None``).
    """

    side, attribute = parse_field(dotted)
    if side in _PERSON_SIDES:
        raise ValueError(
            f"{dotted!r} is multi-valued; read it with get_field_values"
        )
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


def get_field_values(
    dotted: str, *, reviewer: object, reviewee: object
) -> tuple[str, ...]:
    """Every value of ``dotted`` for the pair, empty when it has none.

    A single-valued field gives at most one value (that of
    :func:`get_field_value`). A person-level pair tag
    (``reviewer.pair_tagN`` / ``reviewee.pair_tagN``) gives every value
    that person holds in slot N across their active relationships, in
    no particular order; a person with no such pair gives none.
    """

    side, attribute = parse_field(dotted)
    if side not in _PERSON_SIDES:
        value = get_field_value(dotted, reviewer=reviewer, reviewee=reviewee)
        return () if value is None else (value,)
    person = reviewer if side == "reviewer_pairs" else reviewee
    person_id = getattr(person, "id", None)
    index = _person_index.get()
    if index is None or person_id is None:
        return ()
    return tuple(index.get((side, person_id, attribute), ()))
