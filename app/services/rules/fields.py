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

Segment 15D PR 3 adds the ``pair_context.tag1/2/3`` family. Their
values live on the new ``relationships`` table (one row per
``(session_id, reviewer_id, reviewee_id)`` pair); 15D PR 4 wires
the engine to consult an eager-loaded
``pair_context_lookup: dict[tuple[int, int], Relationship]`` map
keyed on ``(reviewer_id, reviewee_id)``. **Until PR 4 ships,**
``get_field_value`` returns ``None`` for any ``pair_context.*``
field — predicates referencing pair-context evaluate to ``False``
(or ``True`` for ``is_empty`` / ``is_not_empty``) but the engine
does not crash, so PR 3 is safely shippable on its own.
"""

from __future__ import annotations

from typing import Final

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


def get_field_value(
    dotted: str, *, reviewer: object, reviewee: object
) -> str | None:
    """Return the value of ``dotted`` for the given pair.

    Empty strings normalise to ``None`` per spec §9 (empty tag values
    are treated as missing). The engine relies on this so predicates
    referencing a missing field consistently evaluate to ``false``
    unless the operator is ``is_empty``.

    ``pair_context.*`` fields return ``None`` here as a stub; 15D PR
    4 swaps the resolver to consult the eager-loaded
    ``relationships`` lookup the route handler builds before
    ``engine.evaluate()`` runs. See module docstring above.
    """

    side, attribute = parse_field(dotted)
    if side == "pair_context":
        # PR 3 stub — PR 4 wires the real lookup. Returning ``None``
        # makes pair-context predicates evaluate to ``False`` (or
        # ``True`` for ``is_empty``) without crashing the engine.
        return None
    target = reviewer if side == "reviewer" else reviewee
    raw = getattr(target, attribute, None)
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() == "":
        return None
    return raw
