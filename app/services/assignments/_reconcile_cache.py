"""Content stamp for the per-instrument staleness verdict (19R Item 2).

``staleness_by_instrument`` answers *would regenerating change which
pairs exist?* by running the rules engine once per instrument, on every
render. At a 1,000 x 1,000 roster the engine's floor is 2.29 s per
instrument (``guide/app_responsiveness.md``), so the verdict is cached
on ``instruments.cached_reconcile_*`` against a stamp of everything the
verdict is derived from; a mismatch recomputes.

**The stamp must never be the same when the answer could differ.** A
missing input is a wrong "fresh" — and the staleness badge is the
operator's only notice that generated rows no longer match their rules,
a signal ``app/services/validation.py`` records having once been a
no-op that "reports a clean bill on exactly the thing it exists to
catch". Over-covering costs a needless recompute; under-covering lies.
Everything here errs toward the first.

Four groups of inputs, and one non-input:

1. **The rosters**, through :data:`~app.services.rules.fields.FIELD_MAP`
   rather than a hand-written column list, so a newly addressable
   predicate field is covered by the one-row edit its own docstring
   promises is enough.
2. **The relationships rows** behind ``pair_context.tag_N``, including
   ``status``: an inactive row hides its tags from the engine
   ("skip-at-lookup"), so deactivating one can change the fan-out.
3. **The pinned rule**, meaning everything
   ``_session_rule_set_to_schema`` reads off the row plus the
   ``exclude_self_reviews`` flag ``_diff_one_instrument`` reads
   directly.
4. **The instrument and session settings** the diff consults:
   ``rule_set_id``, ``group_kind``, ``self_reviews_active``, and the
   caller's ``override_exclude_self_reviews``.

And the non-input: **the materialized rows themselves**. The verdict is
a *diff* against the instrument's existing ``Assignment`` rows, so
Generate changes the answer while every engine input holds still. A
cached ``stale=True`` would outlive the regenerate that made it fresh.
The write-through in ``replace_assignments`` is the primary answer;
:class:`MaterializedRows` is the backstop that makes an unforeseen
write path invalidate rather than lie.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Relationship,
    ReviewSession,
    Reviewee,
    Reviewer,
    SessionRuleSet,
)
from app.services.rules.fields import FIELD_MAP

#: Prefix on every stamp. Bump it when the *shape* below changes, so a
#: row stamped by an older build reads as a miss instead of colliding
#: with a value computed a different way. It is the reason the column
#: is ``String(80)`` and not the ``String(64)`` a bare digest needs.
STAMP_VERSION = "v1"


@dataclass(frozen=True)
class MaterializedRows:
    """How many ``Assignment`` rows an instrument has, and the highest
    id among them — the cheap component of the row set that no insert
    or delete leaves unchanged.

    It is sufficient for what the verdict reads, which is the *key set*
    ``{(reviewer_id, reviewee_id)}``: a delete moves ``count``, and an
    insert always takes a fresh id above the current ``max_id``, so no
    combination of the two returns to the same pair. Updates to other
    columns move neither, and cannot change the verdict either, since
    the diff keys on those two FKs alone.

    What it would miss is an in-place rewrite of ``reviewer_id`` or
    ``reviewee_id`` on an existing row. Nothing does that — assignment
    rows are replaced, not re-pointed — and this is the backstop
    anyway, behind the write-through.
    """

    count: int
    max_id: int | None


def materialized_rows_by_instrument(
    db: Session, session_id: int
) -> dict[int, MaterializedRows]:
    """``{instrument_id: MaterializedRows}`` for one session, in a
    single grouped aggregate.

    One query for the page rather than one per instrument: the cache
    exists to take a page under a second, and a per-instrument query
    would put back a smaller version of the cost it removes.

    An instrument with no rows is **absent** from the mapping rather
    than present with a zero — ``GROUP BY`` has nothing to group. Use
    :func:`rows_for` to read it, which supplies the empty value.
    """
    stmt = (
        select(
            Assignment.instrument_id,
            func.count(Assignment.id),
            func.max(Assignment.id),
        )
        .where(Assignment.session_id == session_id)
        .group_by(Assignment.instrument_id)
    )
    return {
        instrument_id: MaterializedRows(count=int(count), max_id=max_id)
        for instrument_id, count, max_id in db.execute(stmt)
    }


def rows_for(
    rows_by_instrument: Mapping[int, MaterializedRows], instrument_id: int
) -> MaterializedRows:
    """The instrument's row summary, or the empty one if it has no
    rows. Never-generated and emptied read alike here; the verdict's
    own never-generated rule lives in ``staleness_by_instrument``."""
    return rows_by_instrument.get(
        instrument_id, MaterializedRows(count=0, max_id=None)
    )


def _side_attributes(side: str) -> tuple[str, ...]:
    """ORM attribute names a rule predicate can address on ``side``,
    read off ``FIELD_MAP`` and sorted for determinism.

    Derived rather than listed because ``FIELD_MAP``'s own docstring
    promises that adding an addressable field is "a one-row edit here
    and nowhere else" — a hand-written copy here would quietly make
    that false, and the failure would be a stamp that stays equal
    while the fan-out changes.
    """
    return tuple(
        sorted({attr for mapped_side, attr in FIELD_MAP.values() if mapped_side == side})
    )


def _roster_digest(rows: Iterable[Any], *, side: str) -> list[list[Any]]:
    """One list per row: its id, its ``status``, then every addressable
    attribute for ``side``.

    Sorted by id here rather than trusting the caller's ordering, so
    the stamp does not depend on which query loaded the rows.

    ``status`` is **over-coverage today**: the engine reads the roster
    unfiltered, so deactivating a reviewer does not move the fan-out.
    It is carried because the plan's Semantics commits to it and
    because the cost of being wrong in this direction is one recompute,
    while the cost in the other direction is a badge that lies.
    """
    attributes = _side_attributes(side)
    return [
        [row.id, row.status, *(getattr(row, attr) for attr in attributes)]
        for row in sorted(rows, key=lambda r: r.id)
    ]


def _pair_context_digest(
    lookup: Mapping[tuple[int, int], Relationship],
) -> list[list[Any]]:
    """One list per relationship row, keyed and sorted by
    ``(reviewer_id, reviewee_id)``.

    ``status`` is not over-coverage here: ``fields.get_field_value``
    skips a non-``active`` row, so every ``pair_context.tag_N``
    predicate reads ``None`` against it.
    """
    attributes = _side_attributes("pair_context")
    return [
        [
            key[0],
            key[1],
            row.status,
            *(getattr(row, attr) for attr in attributes),
        ]
        for key, row in sorted(lookup.items())
    ]


def _rule_set_digest(rule_set: SessionRuleSet | None) -> Any:
    """Everything the engine reads off the pinned rule, or ``None`` for
    an unpinned instrument — which is the Full Matrix default at the
    diff site, not an absence.

    The field list is *what the readers read*: ``id``, ``name``,
    ``description``, ``combinator`` and ``rules_json`` reach the engine
    through ``_session_rule_set_to_schema``, and
    ``exclude_self_reviews`` is read by ``_diff_one_instrument`` after
    the fan-out. ``name`` and ``description`` cannot move a pair, but
    they are read, and "what the readers read" is a boundary that can
    be checked against the code; "what could matter" is a judgement
    that goes stale.
    """
    if rule_set is None:
        return None
    return {
        "id": rule_set.id,
        "name": rule_set.name,
        "description": rule_set.description,
        "combinator": rule_set.combinator,
        "exclude_self_reviews": bool(rule_set.exclude_self_reviews),
        "rules": rule_set.rules_json,
    }


def reconcile_stamp(
    *,
    review_session: ReviewSession,
    instrument: Instrument,
    session_rule_set: SessionRuleSet | None,
    reviewers: Sequence[Reviewer],
    reviewees: Sequence[Reviewee],
    pair_context_lookup: Mapping[tuple[int, int], Relationship],
    materialized: MaterializedRows,
    override_exclude_self_reviews: bool | None = None,
) -> str:
    """The stamp for one instrument's reconcile verdict.

    Pure: reads the objects handed to it and touches no database. The
    session-wide parts (the rosters, the relationships) are the same
    for every instrument in one render, so a caller stamping a whole
    page loads them once.

    ``override_exclude_self_reviews`` is a caller's argument rather
    than stored state, and both app callers leave it ``None`` today. It
    is in the stamp so that a future caller passing ``True`` cannot
    read a verdict computed for ``None``.
    """
    payload = {
        "session": {
            "self_reviews_active": bool(review_session.self_reviews_active),
        },
        "instrument": {
            "rule_set_id": instrument.rule_set_id,
            "group_kind": instrument.group_kind,
        },
        "rule_set": _rule_set_digest(session_rule_set),
        "reviewers": _roster_digest(reviewers, side="reviewer"),
        "reviewees": _roster_digest(reviewees, side="reviewee"),
        "pair_context": _pair_context_digest(pair_context_lookup),
        "rows": {
            "count": materialized.count,
            "max_id": materialized.max_id,
        },
        "override_exclude_self_reviews": override_exclude_self_reviews,
    }
    # No ``default=`` fallback: every value above is JSON-native, and
    # a fallback would stringify an unexpected type instead of raising
    # — which is how two different values quietly become one stamp.
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"{STAMP_VERSION}:{hashlib.sha256(encoded).hexdigest()}"
