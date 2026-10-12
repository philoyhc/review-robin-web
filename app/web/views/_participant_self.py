"""What a participant is shown of their own roster entry.

`guide/participant_info.md` Items 1, 3 and 4. Each participant type has
one session-wide selection of its roster fields, shown to that
participant after the role pills on their own pages, chosen in a card on
its roster page's Unlock panel and reported in that page's readout row.

One core, parameterized by a `SelfSpec`, so the reviewer (Item 1) and
reviewee (Item 4) sides cannot drift apart. The selections themselves,
their defaults and their storage live in ``app.services.participant_info``;
this module shapes them for the pages.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.db.models import ReviewSession
from app.services import field_labels as field_labels_service
from app.services.participant_info import (
    REVIEWEE_SELF_DEFAULT,
    REVIEWEE_SELF_FIELD_KEYS,
    REVIEWER_SELF_DEFAULT,
    REVIEWER_SELF_FIELD_KEYS,
)

from ._setup import ColumnReadout

__all__ = [
    "REVIEWEE_SPEC",
    "REVIEWER_SPEC",
    "SelfFieldChip",
    "SelfFieldValue",
    "SelfSpec",
    "self_chips",
    "self_kept",
    "self_label",
    "self_line",
    "self_readout",
]


@dataclass(frozen=True)
class SelfSpec:
    """One participant type's own-entry fields."""

    #: The `field_labels` source a tag's friendly label is read under.
    source_type: str
    #: Every field the participant can be shown, in roster order.
    keys: tuple[str, ...]
    #: The selection while none is stored.
    default: tuple[str, ...]
    #: The roster index names its readouts by the preview table's chip
    #: slots; the selection uses the model's column names.
    slot_to_key: dict[str, str] = field(default_factory=dict)
    #: The fixed columns' operator-facing names; a tag's is its label.
    fixed_labels: dict[str, str] = field(default_factory=dict)


_TAG_SLOTS = {f"tag-{n}": f"tag_{n}" for n in (1, 2, 3)}

REVIEWER_SPEC = SelfSpec(
    source_type="reviewer",
    keys=REVIEWER_SELF_FIELD_KEYS,
    default=REVIEWER_SELF_DEFAULT,
    slot_to_key={
        "name": "name", "email": "email", "profile": "profile_link",
        **_TAG_SLOTS,
    },
    fixed_labels={"name": "Name", "email": "Email", "profile_link": "Profile"},
)

REVIEWEE_SPEC = SelfSpec(
    source_type="reviewee",
    keys=REVIEWEE_SELF_FIELD_KEYS,
    default=REVIEWEE_SELF_DEFAULT,
    slot_to_key={
        "name": "name", "email": "email_or_identifier",
        "profile": "profile_link", **_TAG_SLOTS,
    },
    fixed_labels={
        "name": "Name", "email_or_identifier": "Email",
        "profile_link": "Profile",
    },
)


@dataclass(frozen=True)
class SelfFieldChip:
    """One selector chip on an Unlock panel's own-entry card."""

    key: str
    label: str
    selected: bool


@dataclass(frozen=True)
class SelfFieldValue:
    """One field of a participant's own line on their page."""

    key: str
    label: str
    value: str


def self_label(spec: SelfSpec, review_session: ReviewSession, key: str) -> str:
    """The field's operator-facing name: a literal for a fixed column,
    the friendly label for a tag, as the roster index reads."""
    if key in spec.fixed_labels:
        return spec.fixed_labels[key]
    return field_labels_service.resolve_pair(
        review_session, spec.source_type, key
    ).friendly


def self_chips(
    spec: SelfSpec, readouts: Iterable[ColumnReadout], selected: Iterable[str]
) -> list[SelfFieldChip]:
    """One chip per populated column, in roster order, under the label
    the roster index already gives it."""
    chosen = set(selected)
    return [
        SelfFieldChip(
            key=spec.slot_to_key[r.slot],
            label=r.label,
            selected=spec.slot_to_key[r.slot] in chosen,
        )
        for r in readouts
        if r.slot in spec.slot_to_key
    ]


def self_kept(
    spec: SelfSpec, chips: Iterable[SelfFieldChip], selected: Iterable[str]
) -> list[str]:
    """Selected keys the card offers no chip for (no data in that
    column), in roster order: the card posts them back as hidden
    ``keep`` inputs so a save does not drop them."""
    offered = {chip.key for chip in chips}
    chosen = set(selected)
    return [k for k in spec.keys if k in chosen and k not in offered]


def self_readout(
    spec: SelfSpec, review_session: ReviewSession, selected: Iterable[str]
) -> list[str]:
    """The roster card's `… see:` pills, in roster order."""
    chosen = set(selected)
    return [
        self_label(spec, review_session, k) for k in spec.keys if k in chosen
    ]


def self_line(
    spec: SelfSpec,
    review_session: ReviewSession,
    row: object,
    selected: Iterable[str],
) -> list[SelfFieldValue]:
    """The selected fields of this participant's own row, in roster
    order; a field empty on the row is skipped."""
    chosen = set(selected)
    line: list[SelfFieldValue] = []
    for key in spec.keys:
        if key not in chosen:
            continue
        value = getattr(row, key) or ""
        if not value.strip():
            continue
        line.append(
            SelfFieldValue(
                key=key, label=self_label(spec, review_session, key), value=value
            )
        )
    return line
