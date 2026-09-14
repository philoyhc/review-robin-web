"""Cross-service query helpers.

Tiny shared primitives that don't fit any one service module's
domain. Per ``guide/archive/major_refactor.md`` §12.C.3: introduces a
single audit point for the most-repeated where-clause pattern in
the service layer (~38 callsites across 8 files as of 2026-05-09);
saves ~3 lines per callsite, and gives the codebase one place to
look if the ``session_id`` column is ever renamed.

The helper is deliberately narrow: it returns a partially-applied
``select(model)`` filtered by ``session_id``, leaving the caller
to chain ``.order_by(...)`` / ``.limit(...)`` / extra ``.where(...)``
clauses as usual. No ``execute`` / ``scalar(s)`` ergonomics — the
caller already owns the ``Session`` and decides how to consume the
result.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select


def session_scoped(target: Any, session_id: int) -> Select[Any]:
    """``select(target).where(<model>.session_id == session_id)`` —
    pre-filter a select against the session boundary.

    ``target`` may be either a mapped class (e.g. ``Reviewer``) or a
    column attribute on one (e.g. ``Reviewer.id``,
    ``Assignment.context``). The model whose ``session_id`` is
    filtered is inferred from ``target`` — either ``target`` itself
    when it's a class, or ``target.class_`` when it's a column.
    Use as e.g.
    ``db.execute(session_scoped(Reviewer, sid).order_by(...))``.

    Doesn't handle ``delete(Model)`` chains or composite selects
    where multiple models bring their own ``session_id``; those stay
    on the bare ``select(...).where(Model.session_id == ...)``
    pattern.
    """
    model = target if isinstance(target, type) else target.class_
    return select(target).where(model.session_id == session_id)


def slot_has_data(
    db: Any,
    *,
    session_id: int,
    column: Any,
    active_only: bool = False,
) -> bool:
    """``True`` iff at least one row of ``column``'s model for this
    session has a non-empty value in ``column`` (non-NULL and not the
    empty string).

    Shared primitive used by:

    - The Setup pages' "Fields with data" pills
      (``app.services.assignments.reviewer_fields_with_data`` etc.).
    - Band 1's tag-slot dropdowns on the new-model instrument card
      (``app.web.views._instruments.new_model_usable_tags``).
    - Band 2's "Review Instrument" preview pills
      (``app.web.views._instruments._new_model_band2_state``).

    ``active_only=True`` restricts to rows where ``status == "active"``,
    matching the rule engine's view of pair-context tags (only active
    relationships contribute predicate values). Setup-page callers
    leave it ``False`` — they show imported data regardless of status.
    """
    model = column.class_
    q = (
        select(model.id)
        .where(model.session_id == session_id)
        .where(column.is_not(None))
        .where(column != "")
    )
    if active_only:
        q = q.where(model.status == "active")
    return db.execute(q.limit(1)).first() is not None


def tag_slot_presence(
    db: Any,
    *,
    session_id: int,
    model: Any,
    active_only: bool = False,
) -> dict[str, bool]:
    """``{"tag_1": bool, "tag_2": bool, "tag_3": bool}`` for a
    session's rows of ``model``.

    Three :func:`slot_has_data` calls, which is three indexed
    ``LIMIT 1``s — the same primitive the "Fields with data" pills
    were built on, and the reason Segment 19I Item 12 could make the
    column chips answer over the **whole roster** rather than over
    whichever rows the page happened to be rendering.

    That distinction was not cosmetic. Before Item 12 every one of
    the six chip surfaces scanned its own row list in Jinja, and
    every one of them could therefore be wrong:

    - the three Setup rosters scanned the **filtered and capped**
      display list, so a tag populated only past the 200/500 window,
      or only on rows a filter excluded, read as "no data";
    - Invitations and Responses scanned the filtered set;
    - Assignments deliberately used an *unfiltered* sample and was
      still capped at ``PAIR_PREVIEW_LIMIT``.

    ``active_only=True`` restricts to ``status == "active"`` rows.
    Assignments passes it for pair-context tags, matching the rule
    engine's view (only active relationships contribute predicate
    values); the Relationships Setup page does not, because it shows
    imported data regardless of status. The two answers differ on
    purpose.
    """
    return {
        f"tag_{slot}": slot_has_data(
            db,
            session_id=session_id,
            column=getattr(model, f"tag_{slot}"),
            active_only=active_only,
        )
        for slot in (1, 2, 3)
    }
