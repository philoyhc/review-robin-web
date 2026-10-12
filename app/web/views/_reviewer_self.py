"""What a reviewer is shown of their own roster entry (participant info Item 1).

`guide/participant_info.md` Item 1. One session-wide selection of a
reviewer's roster fields, shown to that reviewer after the role pills on
the reviewer surface and its operator preview, chosen on the Reviewers
page's Unlock panel and reported in its roster card's readout row.

Rung 2 is the scaffold: nothing stores a selection yet, so every caller
passes the default, which is what a stored ``NULL`` will mean.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.db.models import Reviewer, ReviewSession
from app.services import field_labels as field_labels_service

from ._setup import ColumnReadout

#: Every field a reviewer can be shown of themselves, in roster order.
REVIEWER_SELF_FIELD_KEYS: tuple[str, ...] = (
    "name",
    "email",
    "profile_link",
    "tag_1",
    "tag_2",
    "tag_3",
)

#: The selection while none is stored: tags can be shown but start off.
REVIEWER_SELF_DEFAULT: tuple[str, ...] = ("name", "email", "profile_link")

# `reviewer_column_state` names its readouts by the preview table's chip
# slots; the selection uses the model's column names.
_SLOT_TO_KEY = {
    "name": "name",
    "email": "email",
    "profile": "profile_link",
    "tag-1": "tag_1",
    "tag-2": "tag_2",
    "tag-3": "tag_3",
}


@dataclass(frozen=True)
class SelfFieldChip:
    """One selector chip on the Unlock panel's card."""

    key: str
    label: str
    selected: bool


@dataclass(frozen=True)
class SelfFieldValue:
    """One field of the reviewer's own line on the surface."""

    key: str
    label: str
    value: str


def reviewer_self_label(review_session: ReviewSession, key: str) -> str:
    """The field's operator-facing name: a literal for the three fixed
    columns, the friendly label for a tag, as the roster index reads."""
    if key == "name":
        return "Name"
    if key == "email":
        return "Email"
    if key == "profile_link":
        return "Profile"
    return field_labels_service.resolve_pair(
        review_session, "reviewer", key
    ).friendly


def reviewer_self_chips(
    readouts: Iterable[ColumnReadout], selected: Iterable[str]
) -> list[SelfFieldChip]:
    """One chip per populated column, in roster order.

    ``readouts`` is ``reviewer_column_state(...).readouts``: Name and
    Email always, Profile and each tag only while some row holds a value,
    each already under its operator-facing label.
    """
    chosen = set(selected)
    return [
        SelfFieldChip(
            key=_SLOT_TO_KEY[r.slot],
            label=r.label,
            selected=_SLOT_TO_KEY[r.slot] in chosen,
        )
        for r in readouts
        if r.slot in _SLOT_TO_KEY
    ]


def reviewer_self_readout(
    review_session: ReviewSession, selected: Iterable[str]
) -> list[str]:
    """The roster card's `Shown on surface:` pills, in roster order."""
    chosen = set(selected)
    return [
        reviewer_self_label(review_session, key)
        for key in REVIEWER_SELF_FIELD_KEYS
        if key in chosen
    ]


def reviewer_self_line(
    review_session: ReviewSession,
    reviewer: Reviewer,
    selected: Iterable[str],
) -> list[SelfFieldValue]:
    """The selected fields of this reviewer's own row, in roster order;
    a field empty on the row is skipped."""
    chosen = set(selected)
    line: list[SelfFieldValue] = []
    for key in REVIEWER_SELF_FIELD_KEYS:
        if key not in chosen:
            continue
        value = getattr(reviewer, key) or ""
        if not value.strip():
            continue
        line.append(
            SelfFieldValue(
                key=key,
                label=reviewer_self_label(review_session, key),
                value=value,
            )
        )
    return line
