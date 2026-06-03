"""Per-page status rollups for the reviewer-surface overview card.

Pure functions — they take built row dicts and return a single
state literal each. Stateless; no DB reads. Used by ``_context``
when assembling the template context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PageStatusState = Literal["not_started", "in_progress", "complete", "submitted"]


@dataclass(frozen=True)
class PageStatus:
    """Per-page completion status for the right-half status panel.

    Lands in template context as ``page_statuses: list[PageStatus]``,
    one entry per instrument the reviewer has assignments on. Single-
    instrument sessions still get one entry — the panel always
    renders. Operator preview passes an empty list (per-page state
    is moot for synthetic preview rows).
    """

    position: int
    label: str  # "#N {short_label}" when set, else bare "#N"
    state: PageStatusState


def _page_status_for_group(group_rows: list[dict]) -> PageStatusState:
    """Roll up per-row completion data into a single page state.

    Order of evaluation matches the spec table in
    ``spec/reviewer-surface.md`` "Per-page status":

    1. ``submitted`` — every row has ``submitted_at`` set. Submit is
       a hard gate on missing-required, so ``submitted`` implies
       ``complete`` today; the two states are kept separate so a
       future operator-side ``required`` change after submit
       doesn't silently demote the row from ``submitted``.
    2. ``complete`` — every required field on every row has a saved
       value (``is_complete``).
    3. ``in_progress`` — at least one row carries Response data,
       but neither ``submitted`` nor ``complete`` apply.
    4. ``not_started`` — no Response data on any row.

    ``in_progress`` falls back to "any row has at least one cell
    with a non-empty value" — a Response row can exist with an
    empty string, but that's the same shape as "not started" for
    pill-display purposes.
    """
    if not group_rows:
        return "not_started"
    if all(r.get("submitted_at") for r in group_rows):
        return "submitted"
    if all(r.get("is_complete") for r in group_rows):
        return "complete"
    has_any_value = any(
        any((cell.get("value") or "") for cell in r.get("cells", []))
        for r in group_rows
    )
    return "in_progress" if has_any_value else "not_started"


SessionStatusState = Literal["draft", "saved", "submitted"]


def _session_status(page_statuses: list["PageStatus"]) -> SessionStatusState | None:
    """Roll the per-page states into one session-wide status.

    ``submitted`` — every page submitted; ``draft`` — nothing started
    on any page; ``saved`` — anything in between (some saved but not
    all submitted). ``None`` when the reviewer has no pages, so the
    template renders no session pill.
    """
    if not page_statuses:
        return None
    states = {ps.state for ps in page_statuses}
    if states == {"submitted"}:
        return "submitted"
    if states == {"not_started"}:
        return "draft"
    return "saved"


@dataclass(frozen=True)
class GroupCompletion:
    """Per-instrument response-cell completion tallies for the
    Page-card progress pills. An "item" is one response cell — a
    single field for one reviewee. ``required_*`` counts cells whose
    field is required; ``all_*`` counts every response cell.
    """

    required_done: int
    required_total: int
    all_done: int
    all_total: int


def _group_completion(group_rows: list[dict], fields: list) -> GroupCompletion:
    """Tally completed vs total response cells for one instrument.

    ``required_done`` is derived from each row's ``missing_count``
    (DB-accurate); ``all_done`` counts display-cell values, which
    matches what the reviewer sees on a live surface.
    """
    n_rows = len(group_rows)
    required_field_count = sum(1 for f in fields if f.required)
    required_total = required_field_count * n_rows
    required_done = required_total - sum(
        r.get("missing_count", 0) for r in group_rows
    )
    all_total = len(fields) * n_rows
    all_done = sum(
        1
        for r in group_rows
        for cell in r.get("cells", [])
        if (cell.get("value") or "").strip()
    )
    return GroupCompletion(
        required_done=required_done,
        required_total=required_total,
        all_done=all_done,
        all_total=all_total,
    )
