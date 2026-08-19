"""Reviewer-progress pill styling — one source for state → (css, label).

The reviewer's whole-session / per-page progress state (`not started` /
`in progress` / `submitted`) was rendered by four templates, each
hand-rolling its own pill class + label, so the *same* state drew
differently — "submitted" green on the dashboard but blue on the operator
invitations table, "not started" blue on the dashboard but amber on the
reviewer surface — and the value arrived under two spellings
(space-separated `in progress` from monitoring vs underscore `in_progress`
from the surface). This helper is the single mapping (audit V2).

Exposed as a Jinja global `progress_pill` on both the operator and
reviewer template instances (see the two `routes_*/_shared.py`), so any
template renders a consistent pill with
``<span class="pill {{ progress_pill(state).css }}">…</span>``. The
canonical colour semantic follows the reviewer dashboard's original
legend — **blue = nothing yet, amber = mid-flight, green = done**.
"""

from __future__ import annotations

from typing import NamedTuple


class ProgressPill(NamedTuple):
    css: str
    label: str


# Canonical (space-separated) state → pill. ``complete`` is the reviewer
# surface's page-level "all required fields filled but not yet submitted"
# state — distinct from ``submitted`` (both green, but kept as their own
# labels).
_BY_STATE: dict[str, ProgressPill] = {
    "submitted": ProgressPill("pill-success", "submitted"),
    "complete": ProgressPill("pill-success", "complete"),
    "in progress": ProgressPill("pill-warning", "in progress"),
    "not started": ProgressPill("pill-info", "not started"),
}

_NOT_STARTED = ProgressPill("pill-info", "not started")


def progress_pill(state: str | None) -> ProgressPill:
    """Map a reviewer-progress state to its canonical pill ``(css,
    label)``. Normalises both enum spellings (underscore or space) and
    falls back to the "not started" pill for an empty / unknown state."""
    key = (state or "").strip().lower().replace("_", " ")
    return _BY_STATE.get(key, _NOT_STARTED)
