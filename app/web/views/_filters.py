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

import json
import re
from typing import Any

from ._invitations import InvitationsRow
from ._responses import ResponsesRow

from app.db.models import Observer, Relationship, Reviewee, Reviewer

# Cap for the per-page `<datalist>` autocomplete options. Decision 14
# in ``guide/segment_15F_enhanced_setup_pages.md`` — the
# autocomplete suggestions are a convenience, not the search itself;
# the server-side filter still handles anything the operator types
# beyond the first 200 alphabetical matches.
REVIEWERS_DATALIST_CAP: int = 200


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


# Status filter options for the Reviewers Setup page. Order matters
# (dropdown order operators see). ``"all"`` is implicit (no filter).
# Segment 15F PR 2.
REVIEWERS_STATUS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("active", "Active"),
    ("inactive", "Inactive"),
)


def filter_reviewers_rows(
    rows: list[Reviewer], *, status: str, search: str
) -> list[Reviewer]:
    """Apply status + search filters to a Reviewer list.

    ``status`` is one of ``REVIEWERS_STATUS_OPTIONS`` keys
    (``"active"`` / ``"inactive"``) or ``"all"`` (anything else
    falls through to ``"all"``). ``search`` is matched
    case-insensitively against the reviewer's name or email; when
    the value looks like a ``"Name (email)"`` typeahead pick, the
    bracketed email is used for an exact match instead. Empty
    ``search`` is a no-op."""
    out = list(rows)
    valid_status = {key for key, _ in REVIEWERS_STATUS_OPTIONS}
    if status in valid_status:
        out = [r for r in out if r.status == status]
    needle = search.strip()
    if needle:
        tail = _extract_filter_label_tail(needle)
        if tail is not None and "@" in tail:
            picked = tail.casefold()
            out = [r for r in out if r.email.casefold() == picked]
        else:
            out = [
                r
                for r in out
                if _matches_search(r.name, needle)
                or _matches_search(r.email, needle)
            ]
    return out


def reviewers_search_options(rows: list[Reviewer]) -> list[str]:
    """``"Name (email)"`` labels for the Reviewers page typeahead.

    Sorted alphabetically (case-insensitive); capped at
    ``REVIEWERS_DATALIST_CAP`` per decision 14 in
    ``guide/segment_15F_enhanced_setup_pages.md`` — the autocomplete
    suggestions are a convenience, the server-side filter handles
    anything the operator types beyond the first N matches."""
    labels = sorted(
        (f"{r.name} ({r.email})" for r in rows),
        key=str.casefold,
    )
    return labels[:REVIEWERS_DATALIST_CAP]


# Status filter options for the Reviewees Setup page. Order matters
# (dropdown order operators see). ``"all"`` is implicit. Segment 15F
# PR 4 — same shape as ``REVIEWERS_STATUS_OPTIONS``.
REVIEWEES_STATUS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("active", "Active"),
    ("inactive", "Inactive"),
)


def filter_reviewees_rows(
    rows: list[Reviewee], *, status: str, search: str
) -> list[Reviewee]:
    """Apply status + search filters to a Reviewee list.

    ``status`` is one of ``REVIEWEES_STATUS_OPTIONS`` keys
    (``"active"`` / ``"inactive"``) or ``"all"``. ``search`` is
    matched case-insensitively against the reviewee's name or
    ``email_or_identifier``; when the value looks like a
    ``"Name (identifier)"`` typeahead pick, the bracketed handle is
    used for an exact match instead. Empty ``search`` is a no-op."""
    out = list(rows)
    valid_status = {key for key, _ in REVIEWEES_STATUS_OPTIONS}
    if status in valid_status:
        out = [r for r in out if r.status == status]
    needle = search.strip()
    if needle:
        tail = _extract_filter_label_tail(needle)
        if tail is not None:
            picked = tail.casefold()
            out = [
                r
                for r in out
                if r.email_or_identifier.casefold() == picked
            ]
        else:
            out = [
                r
                for r in out
                if _matches_search(r.name, needle)
                or _matches_search(r.email_or_identifier, needle)
            ]
    return out


def reviewees_search_options(rows: list[Reviewee]) -> list[str]:
    """``"Name (identifier)"`` labels for the Reviewees page
    typeahead. Sorted alphabetically; capped at
    ``REVIEWERS_DATALIST_CAP`` per decision 14."""
    labels = sorted(
        (f"{r.name} ({r.email_or_identifier})" for r in rows),
        key=str.casefold,
    )
    return labels[:REVIEWERS_DATALIST_CAP]


# Status filter options for the Observers Setup page. Mirrors the
# reviewer / reviewee shape — observers carry the same active /
# inactive status flag.
OBSERVERS_STATUS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("active", "Active"),
    ("inactive", "Inactive"),
)


def filter_observers_rows(
    rows: list[Observer], *, status: str, search: str
) -> list[Observer]:
    """Apply status + search filters to an Observer list.

    ``status`` is one of ``OBSERVERS_STATUS_OPTIONS`` keys
    (``"active"`` / ``"inactive"``) or ``"all"``. ``search`` is
    matched case-insensitively against the observer's display
    name or email; when the value looks like a
    ``"Name (email)"`` typeahead pick, the bracketed email is
    used for an exact match instead."""
    out = list(rows)
    valid_status = {key for key, _ in OBSERVERS_STATUS_OPTIONS}
    if status in valid_status:
        out = [o for o in out if o.status == status]
    needle = search.strip()
    if needle:
        tail = _extract_filter_label_tail(needle)
        if tail is not None and "@" in tail:
            picked = tail.casefold()
            out = [o for o in out if o.email.casefold() == picked]
        else:
            out = [
                o
                for o in out
                if _matches_search(o.display_name or "", needle)
                or _matches_search(o.email, needle)
            ]
    return out


def observers_search_options(rows: list[Observer]) -> list[str]:
    """``"Name (email)"`` labels for the Observers page
    typeahead. Sorted alphabetically; capped at
    ``REVIEWERS_DATALIST_CAP``. Falls back to bare email when no
    display name is set."""
    labels = sorted(
        (
            f"{o.display_name} ({o.email})" if o.display_name else o.email
            for o in rows
        ),
        key=str.casefold,
    )
    return labels[:REVIEWERS_DATALIST_CAP]


# Relationships Setup page (Segment 15F PR 5). The dropdown picks
# which side of the pair the search box matches — a relationship
# row has two identity columns, so the operator says which one.
# ``"all"`` is *not* offered: a search always targets one side.
RELATIONSHIPS_SEARCH_BY_OPTIONS: tuple[tuple[str, str], ...] = (
    ("reviewer", "Reviewer"),
    ("reviewee", "Reviewee"),
)


def _relationship_person(
    row: Relationship,
    *,
    dimension: str,
    reviewer_by_id: dict[int, Reviewer],
    reviewee_by_id: dict[int, Reviewee],
) -> tuple[object | None, str | None]:
    """Resolve the (person, handle) for one side of a relationship
    row. ``handle`` is the email (reviewer) or email_or_identifier
    (reviewee). Either may be ``None`` when the FK is dangling."""
    if dimension == "reviewee":
        person = reviewee_by_id.get(row.reviewee_id)
        return person, (person.email_or_identifier if person else None)
    person = reviewer_by_id.get(row.reviewer_id)
    return person, (person.email if person else None)


def filter_relationships_rows(
    rows: list[Relationship],
    *,
    reviewer_by_id: dict[int, Reviewer],
    reviewee_by_id: dict[int, Reviewee],
    search_by: str,
    search: str,
) -> list[Relationship]:
    """Filter relationship rows by one side of the pair.

    ``search_by`` is ``"reviewer"`` or ``"reviewee"`` (anything else
    falls through to ``"reviewer"``). ``search`` matches
    case-insensitively against that side's name or handle; a
    ``"Name (handle)"`` typeahead pick exact-matches the handle.
    Empty ``search`` is a no-op."""
    needle = search.strip()
    if not needle:
        return list(rows)
    dimension = search_by if search_by == "reviewee" else "reviewer"
    tail = _extract_filter_label_tail(needle)
    out: list[Relationship] = []
    for row in rows:
        person, handle = _relationship_person(
            row,
            dimension=dimension,
            reviewer_by_id=reviewer_by_id,
            reviewee_by_id=reviewee_by_id,
        )
        if person is None or handle is None:
            continue
        if tail is not None:
            if handle.casefold() == tail.casefold():
                out.append(row)
        elif _matches_search(person.name, needle) or _matches_search(
            handle, needle
        ):
            out.append(row)
    return out


def relationships_search_options(
    rows: list[Relationship],
    *,
    reviewer_by_id: dict[int, Reviewer],
    reviewee_by_id: dict[int, Reviewee],
    search_by: str,
) -> list[str]:
    """``"Name (handle)"`` labels for the Relationships typeahead,
    built for the currently-selected ``search_by`` dimension. One
    entry per distinct individual appearing in ``rows``; sorted,
    capped at ``REVIEWERS_DATALIST_CAP``."""
    dimension = search_by if search_by == "reviewee" else "reviewer"
    seen: dict[int, str] = {}
    for row in rows:
        person, handle = _relationship_person(
            row,
            dimension=dimension,
            reviewer_by_id=reviewer_by_id,
            reviewee_by_id=reviewee_by_id,
        )
        if person is None or handle is None:
            continue
        seen[person.id] = f"{person.name} ({handle})"
    return sorted(seen.values(), key=str.casefold)[:REVIEWERS_DATALIST_CAP]


# ── Cohort match rule — observer-row view helpers ─────────────────────


_COHORT_OBSERVER_FRIENDLY: dict[str, str] = {
    "observer.name": "Observer: Name",
    "observer.email": "Observer: Email",
    "observer.tag1": "Observer: Tag 1",
}


def cohort_rule_signature(rule: dict[str, Any] | None) -> str:
    """Stable string key for one observer's saved cohort rule.

    Two observers share the same effective rule iff their
    signatures match — used by the Observers Setup page's
    mixed-state JS to decide whether the editor loads a shared
    rule or shows the "differ — saving overwrites" message.

    ``None`` (no rule saved) maps to ``""`` so the JS distinct-
    count check treats unset observers as a single shared
    "empty" group rather than as N distinct rules.
    """
    if rule is None:
        return ""
    return json.dumps(rule, sort_keys=True, ensure_ascii=False)


def _cohort_field_friendly(
    canonical_key: str,
    tag_labels: dict[str, list[tuple[str, str]]],
) -> str:
    """Resolve a ``reviewer.tag1`` / ``observer.email`` / etc.
    canonical key into the operator's friendly label, falling
    back to the canonical key itself when nothing matches (e.g.
    the slot's tag has since been cleared)."""
    if canonical_key in _COHORT_OBSERVER_FRIENDLY:
        return _COHORT_OBSERVER_FRIENDLY[canonical_key]
    for namespace, prefix in (
        ("reviewer", "Reviewer: "),
        ("reviewee", "Reviewee: "),
        ("pair_context", "Pair Context: "),
    ):
        for key, friendly in tag_labels.get(namespace, []):
            if key == canonical_key:
                return prefix + friendly
    return canonical_key


def cohort_rule_summary(
    rule: dict[str, Any] | None,
    *,
    tag_labels: dict[str, list[tuple[str, str]]],
) -> str:
    """One-line summary of the first rule on a saved cohort
    payload, suffixed with ``+ N more`` when extra rules exist.

    Returns ``""`` when ``rule`` is ``None`` or carries no rule
    cells — the Cohort cell falls back to the ``—`` placeholder
    in those cases.
    """
    if not rule:
        return ""
    rules = rule.get("rules") or []
    if not rules:
        return ""
    first = rules[0]
    field = _cohort_field_friendly(str(first.get("field", "")), tag_labels)
    op = str(first.get("op", ""))
    if op in ("IS THE SAME AS", "IS DIFFERENT FROM"):
        operand = _cohort_field_friendly(
            str(first.get("operand_tag", "")), tag_labels
        )
    else:
        operand_value = str(first.get("operand_value", ""))
        operand = f"“{operand_value}”" if operand_value else "“”"
    summary = f"{field} {op} {operand}".strip()
    extra = len(rules) - 1
    if extra > 0:
        summary += f" + {extra} more"
    return summary
