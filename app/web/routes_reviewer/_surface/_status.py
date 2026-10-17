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
    renders. Operator preview builds the list the same way, from the
    previewed reviewer's rows. Preview does not apply the reviewer's
    read-back policy, so after close a page whose saved values the
    reviewer may no longer see can show ``in_progress`` there where
    the reviewer sees ``not_started``.
    """

    position: int
    label: str  # "#N {short_label}" when set, else bare "#N"
    state: PageStatusState


@dataclass(frozen=True)
class _SavedState:
    """What a set of built rows' saved answers say, read off the saved
    Response rows rather than the shown values (findings R7).

    The same three facts drive the dashboard's pill
    (``responses.RollupParts.pill_state``): whether any answer is saved,
    whether every required field is filled, and whether any saved answer
    lacks a ``submitted_at``.
    """

    answered: bool
    required_met: bool
    unsubmitted: bool

    @property
    def submitted(self) -> bool:
        """The dashboard's ``submitted``: something saved, nothing
        required missing, and nothing saved left unsubmitted."""
        return self.answered and self.required_met and not self.unsubmitted


def _saved_state(rows: list[dict]) -> _SavedState:
    return _SavedState(
        answered=any(r.get("answer_count", 0) for r in rows),
        required_met=all(r.get("is_complete") for r in rows),
        unsubmitted=any(r.get("unsubmitted_count", 0) for r in rows),
    )


def _page_status_for_group(group_rows: list[dict]) -> PageStatusState:
    """Roll up per-row completion data into a single page state.

    Order of evaluation matches the spec table in
    ``spec/reviewer-surface.md`` "Per-page status". It is the
    dashboard's answers-based rule (findings R7, author's ruling
    2026-10-17), with ``complete`` splitting the dashboard's
    ``in progress`` where every required field is filled:

    1. ``submitted`` — at least one saved answer, every required field
       filled, and no saved answer without ``submitted_at``. A row left
       blank on an all-optional instrument does not hold it off, as it
       doesn't on the dashboard; a new or changed answer after Submit
       (findings R1) does.
    2. ``complete`` — at least one saved answer and every required
       field filled, with something not yet submitted.
    3. ``in_progress`` — at least one non-empty value shown.
    4. ``not_started`` — none. A page with no answer is not started even
       when nothing on it is required.

    ``submitted`` and ``complete`` read the saved rows; ``in_progress``
    reads the shown cells, so a saved value the reviewer may not read
    back counts as none there.
    """
    if not group_rows:
        return "not_started"
    saved = _saved_state(group_rows)
    if saved.submitted:
        return "submitted"
    if saved.answered and saved.required_met:
        return "complete"
    has_any_value = any(
        any((cell.get("value") or "") for cell in r.get("cells", []))
        for r in group_rows
    )
    return "in_progress" if has_any_value else "not_started"


SessionStatusState = Literal["draft", "saved", "submitted"]


def _session_status(
    page_statuses: list["PageStatus"], rows: list[dict]
) -> SessionStatusState | None:
    """Roll the per-page states into one session-wide status.

    ``submitted`` — the dashboard's rule over ``rows``, every row on
    every page (``_SavedState.submitted``), so a page left blank with
    nothing on it required doesn't hold it off (findings R7). ``draft`` — nothing started on any page; ``saved``
    — anything in between. ``None`` when the reviewer has no pages, so
    the template renders no session pill.
    """
    if not page_statuses:
        return None
    states = {ps.state for ps in page_statuses}
    if _saved_state(rows).submitted:
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

    19T Item 11 — ``required_total`` sums each row's ``required_count``,
    the fields that row must answer, since a required governed field
    counts only while its branch is open. It comes from the same saved
    state as ``missing_count``, so done never exceeds the total. A row
    built without it counts every required field, as before.
    """
    required_field_count = sum(1 for f in fields if f.required)
    required_total = sum(
        r.get("required_count", required_field_count) for r in group_rows
    )
    required_done = required_total - sum(
        r.get("missing_count", 0) for r in group_rows
    )
    # 19T Item 10 — a governed cell whose branch is closed can't be
    # answered, so it is not an item: counting it would hold "All items"
    # short of complete for good.
    open_cells = [
        cell
        for r in group_rows
        for cell in r.get("cells", [])
        if cell.get("branch_open", True)
    ]
    all_total = len(open_cells)
    all_done = sum(1 for cell in open_cells if (cell.get("value") or "").strip())
    return GroupCompletion(
        required_done=required_done,
        required_total=required_total,
        all_done=all_done,
        all_total=all_total,
    )
