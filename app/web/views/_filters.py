"""Filter / search helpers shared between Manage Invitations and
Manage Responses (Segment 11C Part 1's list-with-bulk-actions
filter strip pattern per ``spec/operations_renew.md``
"Filtering").

Slice 4 of the §12.B ladder (``guide/archive/major_refactor.md``).

Owns the status-options registries (``INVITATIONS_STATUS_OPTIONS``
/ ``RESPONSES_STATUS_OPTIONS``), the per-page filter applicators
(``filter_invitations_rows`` / ``filter_responses_rows``), and the
typeahead label builders (``invitations_search_options`` /
``responses_search_options``). Filters compose: status + search
narrows to rows matching both. State is page-local — query params
only.

Imports ``InvitationsRow`` / ``ResponsesRow`` from their slices
(``_invitations.py`` / ``_responses.py``).

Source range in pre-PR-4 ``_legacy.py``: lines 1269-1423.
"""

from __future__ import annotations

import re

from ._invitations import InvitationsRow
from ._responses import ResponsesRow


# Status filter options for Manage Invitations. Order matters: it's the
# dropdown order operators see. ``"all"`` (no filter) is implicit.
INVITATIONS_STATUS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("not_sent", "Not yet sent"),
    ("not_started", "Sent, not started"),
    ("in_progress", "In progress"),
    ("submitted", "Submitted"),
)


# Status filter options for Responses. Order matters; ``"all"`` is implicit.
RESPONSES_STATUS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("complete", "Complete"),
    ("adequate", "Adequate"),
    ("at_risk", "At risk"),
    ("no_responses", "No responses"),
)


def _matches_search(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


_FILTER_LABEL_TAIL_RE = re.compile(r"\(([^()]+)\)\s*$")


def _extract_filter_label_tail(value: str) -> str | None:
    """Return the last parens-enclosed segment of a typeahead label.

    Manage Invitations and Manage Responses use a `<datalist>`
    typeahead whose options have the form ``"Name (email)"`` or
    ``"Name (identifier)"``. When the operator picks from the
    typeahead, the form submits the whole label string, which would
    miss a substring match against just the name or email. Extracting
    the parenthetical lets the filter do an exact email/identifier
    match in the picked-from-typeahead case while still falling back to
    substring search when the operator types free text. ``None`` when
    no parens-enclosed tail is present."""
    match = _FILTER_LABEL_TAIL_RE.search(value)
    if match is None:
        return None
    return match.group(1).strip()


def filter_invitations_rows(
    rows: list[InvitationsRow], *, status: str, search: str
) -> list[InvitationsRow]:
    """Apply status + search filters to invitations rows.

    ``status`` is one of ``INVITATIONS_STATUS_OPTIONS`` keys or
    ``"all"`` (anything else falls through to "all"). ``search`` is
    matched case-insensitively against the reviewer's name or email;
    when the value looks like a ``"Name (email)"`` typeahead pick, the
    bracketed email is used for an exact match instead. Empty
    ``search`` is a no-op."""
    out = list(rows)
    valid_status = {key for key, _ in INVITATIONS_STATUS_OPTIONS}
    if status in valid_status:
        out = [r for r in out if r.summary_state == status]
    needle = search.strip()
    if needle:
        tail = _extract_filter_label_tail(needle)
        if tail is not None and "@" in tail:
            picked = tail.casefold()
            out = [r for r in out if r.reviewer.email.casefold() == picked]
        else:
            out = [
                r
                for r in out
                if _matches_search(r.reviewer.name, needle)
                or _matches_search(r.reviewer.email, needle)
            ]
    return out


def filter_responses_rows(
    rows: list[ResponsesRow], *, status: str, search: str
) -> list[ResponsesRow]:
    """Apply status + search filters to responses rows.

    ``status`` is one of ``RESPONSES_STATUS_OPTIONS`` keys or
    ``"all"``. The four status keys are slugged
    (``"at_risk"`` / ``"no_responses"``) for URL-friendliness; this
    helper maps back to the row's ``coverage_state`` (``"at risk"`` /
    ``"no responses"``).

    ``search`` is matched case-insensitively against the reviewee's
    name or ``email_or_identifier``; when the value looks like a
    ``"Name (identifier)"`` typeahead pick, the bracketed identifier
    is used for an exact match instead."""
    out = list(rows)
    status_to_state = {
        "complete": "complete",
        "adequate": "adequate",
        "at_risk": "at risk",
        "no_responses": "no responses",
    }
    target_state = status_to_state.get(status)
    if target_state is not None:
        out = [r for r in out if r.coverage_state == target_state]
    needle = search.strip()
    if needle:
        tail = _extract_filter_label_tail(needle)
        if tail is not None:
            picked = tail.casefold()
            out = [
                r
                for r in out
                if r.reviewee.email_or_identifier.casefold() == picked
            ]
        else:
            out = [
                r
                for r in out
                if _matches_search(r.reviewee.name, needle)
                or _matches_search(r.reviewee.email_or_identifier, needle)
            ]
    return out


def invitations_search_options(rows: list[InvitationsRow]) -> list[str]:
    """``"Name (email)"`` labels for the Manage Invitations typeahead.

    Sorted alphabetically (case-insensitive) so the `<datalist>` reads
    consistently regardless of the row order the page renders in. One
    entry per row; deduplication isn't needed because invitations rows
    are already one-per-reviewer."""
    labels = [
        f"{r.reviewer.name} ({r.reviewer.email})" for r in rows
    ]
    return sorted(labels, key=str.casefold)


def responses_search_options(rows: list[ResponsesRow]) -> list[str]:
    """``"Name (identifier)"`` labels for the Manage Responses typeahead.

    Same shape as ``invitations_search_options`` but keyed on the
    reviewee's ``email_or_identifier`` (which is the operator-visible
    handle for a reviewee even when there's no email on file)."""
    labels = [
        f"{r.reviewee.name} ({r.reviewee.email_or_identifier})"
        for r in rows
    ]
    return sorted(labels, key=str.casefold)
