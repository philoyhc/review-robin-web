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
